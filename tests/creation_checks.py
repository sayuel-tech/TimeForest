"""Run each creation scenario once and write portable isolated evidence."""
import argparse
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_creation import CreationTests
from tests.test_creation_movie import MovieTests
from tests.test_creation_roundtrip import RoundtripTests

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    suite=unittest.TestSuite();names=[]
    for cls in (CreationTests,MovieTests,RoundtripTests):
        for name in unittest.defaultTestLoader.getTestCaseNames(cls):
            if name not in names:suite.addTest(cls(name));names.append(name)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(tests=result.testsRun,passed=result.wasSuccessful(),scenarios=names,failures=[str(t) for t,_ in result.failures],errors=[str(t) for t,_ in result.errors],environment='temporary stores, external sockets blocked, fake model/media terminals'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
