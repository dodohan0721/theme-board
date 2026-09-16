import unittest
from datetime import datetime, timezone, date
import build_briefing as b
class BriefingTests(unittest.TestCase):
 def test_intraday_is_not_closed_even_with_price(self):
  rows=[{'d':'20260916','p':'100','v':'50'},{'d':'20260915','p':'90','v':'100'},{'d':'20260914','p':'80','v':'110'}]
  got=b.quote_rows(rows,'d','p',date(2026,9,15),'v')
  self.assertEqual([x['date'] for x in got],['2026-09-15','2026-09-14'])
 def test_blank_nan_zero_and_no_volume_rejected(self):
  rows=[{'d':'20260915','p':x,'v':'100'} for x in ['0','','NaN','inf']]+[{'d':'20260914','p':'90','v':'0'}]
  self.assertEqual(b.quote_rows(rows,'d','p',date(2026,9,16),'v'),[])
 def test_rate_calculated_with_actual_previous_session(self):
  q=b.calculated([{'date':'2026-09-15','price':110},{'date':'2026-09-14','price':100}])
  self.assertEqual(q['rate'],10);self.assertEqual(q['change'],10)
 def test_yield_bp_is_difference_not_return(self):
  q=b.calculated([{'date':'2026-09-15','price':5},{'date':'2026-09-14','price':4.97}])
  self.assertAlmostEqual(q['change']*100,3)
 def test_missing_theme_members_are_not_zero(self):
  t={'stocks':['A','B','C','D']}
  q={'A':{'rate':2,'value':5},'B':{'rate':4,'value':2},'C':{'rate':6,'value':3}}
  self.assertEqual(b.aggregate_theme(t,q)['rate'],4)
  self.assertIsNone(b.aggregate_theme(t,{'A':q['A']})['rate'])
 def test_dst_and_winter_close(self):
  self.assertEqual(b.completed_date(datetime(2026,9,16,19,59,tzinfo=timezone.utc)),date(2026,9,15))
  self.assertEqual(b.completed_date(datetime(2026,9,16,20,1,tzinfo=timezone.utc)),date(2026,9,16))
  self.assertEqual(b.completed_date(datetime(2026,12,16,20,59,tzinfo=timezone.utc)),date(2026,12,15))
 def test_past_report_excludes_later_rows(self):
  rows=[{'date':'2026-09-16','price':150},{'date':'2026-09-15','price':110},{'date':'2026-09-14','price':100}]
  self.assertEqual(b.calculated(rows,'2026-09-15')['rate'],10)
 def test_incomplete_report_cannot_replace_valid_report(self):
  with self.assertRaises(ValueError):b.validate({'session_date':'2026-09-15','stats':{'covered_indicators':6,'covered_sectors':11}})
if __name__=='__main__':unittest.main()
