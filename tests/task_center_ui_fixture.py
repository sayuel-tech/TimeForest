"""Real application/task API with temporary data and fake engine; never production."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import jsonify
from tests.test_task_center import TaskCenterTests


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=5098);args=parser.parse_args()
    fixture=TaskCenterTests();fixture.setUp()
    fixture.s.store.mutate('projects',fixture.pid,lambda p:p.update(name='示例项目 · 当前排队'))
    fixture.run_record('a'*32,'waiting')
    fixture.run_record('b'*32,'success')
    old=fixture.s.create('示例项目 · 旧提交')
    fixture.s.store.put('runs',dict(id='c'*32,project=old['id'],task=old['tasks'][0]['id'],state='unknown',prompt_id='old-engine-prompt',created=2,note='原提交结果待确认',seed=0))
    running=fixture.s.create('图片 · 正在生成')
    fixture.s.store.put('runs',dict(id='d'*32,project=running['id'],task=running['tasks'][0]['id'],state='running',prompt_id='fixture-prompt',created=3,note='采样生成',seed=12))
    fixture.get.side_effect=lambda endpoint,**kwargs: {'queue_running':[[0,'fixture-prompt',{}, {'client_id':'time-forest-'+'d'*32}]]} if endpoint=='/queue' else {}
    @fixture.app.get('/__fixture/state')
    def state():
        return jsonify(project=fixture.pid,rows=fixture.s.store.all('runs'),engine_posts=[list(c.args) for c in fixture.post.call_args_list],wakes=fixture.wake.call_count)
    print('Isolated task queue: http://127.0.0.1:'+str(args.port),flush=True)
    try:fixture.app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False)
    finally:fixture.doCleanups()


if __name__=='__main__':main()
