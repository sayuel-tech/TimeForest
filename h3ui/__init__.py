"""Flask 应用工厂。组装配置 + 各模块单例。"""
from flask import Flask

from .config import load_config, ROOT


def create_app(config_path: str | None = None, *, recover_tasks: bool = True):
    app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")
    cfg = load_config(config_path)

    # 运行时上下文: 各模块单例共享
    from . import projects, jobs
    from .comfy import ComfyClient
    ctx = {
        "cfg": cfg,
        "startup_recovery": recover_tasks,
        "image_parameter_contract_version": None,
        "root": ROOT,
        "projects": projects.Registry(cfg),
        "jobs": jobs.JobManager(cfg),
        "comfy": ComfyClient(cfg["comfy_url"], int(cfg.get("job_timeout", 5400))),
    }
    # Legacy projects are read-only in the v5 studio. Do not rewrite their state on startup.
    app.config["H3UI"] = ctx

    from . import routes
    app.register_blueprint(routes.bp)
    from .studio import Studio, bp as studio_bp
    app.config['STUDIO'] = Studio(ctx)
    app.register_blueprint(studio_bp)
    from .prompt_library.service import Library as PromptLibrary
    from .prompt_library.routes import bp as prompt_bp
    from .config import resolve_path
    prompt_root=resolve_path(cfg,'prompt_library_dir') if cfg.get('prompt_library_dir') else app.config['STUDIO'].root/'prompt_library'
    app.config['PROMPT_LIBRARY']=PromptLibrary(prompt_root,app.config['STUDIO'].root/'prompt_receipts',cfg)
    app.config['STUDIO'].prompt_library=app.config['PROMPT_LIBRARY']
    app.register_blueprint(prompt_bp)
    from .asset_library.service import Library
    from .asset_library.routes import bp as library_bp
    from .config import resolve_path
    cfg.setdefault('asset_library_dir', str(ROOT.parent / 'TimeForestAssets'))
    app.config['ASSET_LIBRARY'] = Library(resolve_path(cfg, 'asset_library_dir'), cfg)
    app.config['ASSET_LIBRARY'].attach_tasks(ctx['jobs'], recover_tasks=recover_tasks)
    from .asset_library.project_import import ProjectImport
    importer = ProjectImport(app.config['ASSET_LIBRARY'], app.config['STUDIO'])
    app.config['ASSET_LIBRARY'].project_import = importer
    app.config['ASSET_LIBRARY'].tasks.handlers['project_apply'] = importer.apply
    from .asset_library.results import ResultImports
    results = ResultImports(app.config['ASSET_LIBRARY'], app.config['STUDIO'])
    app.config['ASSET_LIBRARY'].results = results
    app.config['ASSET_LIBRARY'].tasks.handlers['project_result'] = results.import_result
    if recover_tasks and any(x['state'] == 'queued' for x in app.config['ASSET_LIBRARY'].tasks.list()):
        app.config['ASSET_LIBRARY'].tasks.wake()
    app.register_blueprint(library_bp)
    if cfg.get('image_assets_enabled', False):
        from .image_studio.service import ImageStudio
        from .image_studio.routes import bp as image_bp
        from .image_studio.parameters import PARAMETER_CONTRACT_VERSION
        ctx['image_parameter_contract_version'] = PARAMETER_CONTRACT_VERSION
        app.config['IMAGE_STUDIO'] = ImageStudio(app.config['STUDIO'], app.config['ASSET_LIBRARY'])
        app.register_blueprint(image_bp)
        if recover_tasks:
            app.config['IMAGE_STUDIO'].runner.wake()
    from .video_assembly.service import Assembly
    from .video_assembly.routes import bp as assembly_bp
    app.config['VIDEO_ASSEMBLY'] = Assembly(app.config['STUDIO'], app.config['ASSET_LIBRARY'], recover=recover_tasks)
    app.register_blueprint(assembly_bp)
    from .creation.service import Creation
    from .creation.routes import bp as creation_bp
    app.config['CREATION'] = Creation(app.config['STUDIO'], app.config['ASSET_LIBRARY'])
    from .creation.handoffs import Handoffs
    app.config['CREATION'].handoffs = Handoffs(app.config['CREATION'], app.config.get('IMAGE_STUDIO'))
    app.register_blueprint(creation_bp)
    from .task_center import TaskCenter, bp as task_bp
    app.config['TASK_CENTER'] = TaskCenter(app.config['STUDIO'], app.config.get('IMAGE_STUDIO'), app.config['ASSET_LIBRARY'].tasks)
    app.config['TASK_CENTER'].assembly = app.config['VIDEO_ASSEMBLY']
    app.register_blueprint(task_bp)
    from .studio_records import bp as records_bp
    app.register_blueprint(records_bp)
    from .studio_recycle import bp as recycle_bp
    app.register_blueprint(recycle_bp)
    from .generation.recovery import restore_existing
    if recover_tasks:
        restore_existing(app.config['STUDIO'])
    @app.before_request
    def protect_legacy():
        from flask import request, jsonify
        if request.path.startswith('/api/') and not request.path.startswith('/api/v5/') and request.method not in ('GET','HEAD','OPTIONS'):
            return jsonify(error='旧版项目与接口已只读，请在新版工作台建立制作副本'),409
    return app
