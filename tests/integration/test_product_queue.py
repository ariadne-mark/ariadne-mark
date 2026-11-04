import importlib.util,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class ProductQueueTests(unittest.TestCase):
    def test_repeated_worker_death_stops_retrying_and_unblocks_next_job(self):
        path=Path(__file__).parents[2]/'examples/stock_product/app.py'
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PRODUCT_DATA':folder}):
            spec=importlib.util.spec_from_file_location('audit_stock_product',path);app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app);app.init()
            poison,_=app.submit({'fixture':next(iter(app.CATALOG))})
            good,_=app.submit({'fixture':next(iter(app.CATALOG))})
            stage=Path(folder)/'staging'/poison['id'];stage.mkdir();(stage/'partial').write_bytes(b'bad')
            with app.connect() as db:db.execute("UPDATE jobs SET status='processing',attempts=? WHERE id=?",(app.MAX_ATTEMPTS,poison['id']))
            self.assertEqual(app.recover_interrupted_jobs(),[poison['id']])
            self.assertEqual(app.get(poison['id'])['error'],'worker_retry_limit');self.assertFalse(stage.exists())
            self.assertEqual(app.get(good['id'])['status'],'queued')
