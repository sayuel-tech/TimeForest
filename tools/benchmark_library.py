"""Isolated 5000-record library pagination measurement; creates no models or generated video."""
import copy,json,statistics,tempfile,time
from pathlib import Path
from PIL import Image
from h3ui.asset_library.service import Library
from h3ui.asset_library.store import uid,encode

def measure(count=5000):
    with tempfile.TemporaryDirectory(prefix='time-forest-library-bench-') as folder:
        lib=Library(Path(folder)/'library');picture=Path(folder)/'fixture.png';Image.new('RGBA',(64,64),(10,20,30,100)).save(picture)
        example=lib.ingest(picture,'fixture',{'categories':['character'],'tags':['performance']})
        with lib.store.connect() as db:
            header=dict(db.execute('SELECT * FROM assets').fetchone());columns=list(header)
            for i in range(count-1):
                asset=uid();version=uid();data=copy.deepcopy(example['snapshot']);data.update(asset_id=asset,id=version,name=f'性能样本 {i:05}')
                values={**header,'id':asset,'version':version,'name':data['name'],'updated':time.time()}
                db.execute('INSERT INTO assets('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[values[k] for k in columns])
                db.execute('INSERT INTO versions VALUES(?,?,?,?)',(version,asset,time.time(),encode(data)))
                db.execute('INSERT INTO asset_categories VALUES(?,?)',(asset,'character'));db.execute('INSERT INTO tags VALUES(?,?)',(asset,'performance'))
        scenarios={'first_page':{},'last_page':{'page':'139'},'category':{'category':'character'},'search':{'q':'001'},'metadata':{'min_width':'32','aspect':'square'},'tag':{'tag':'performance'}}
        results={}
        for name,filters in scenarios.items():
            timings=[]
            for _ in range(12):
                start=time.perf_counter();result=lib.query(filters);timings.append((time.perf_counter()-start)*1000)
            results[name]=dict(median_ms=round(statistics.median(timings),2),max_ms=round(max(timings),2),page_items=len(result['items']),matching=result['total'])
        return dict(records=count,environment='Windows local SSD; generated metadata and one shared RGBA object; no H3 generation',scenarios=results)
if __name__=='__main__':print(json.dumps(measure(),ensure_ascii=False,indent=2))
