"""Offline mocks: network not contacted."""
import io
import json
import unittest
from unittest.mock import patch
from blackthorn.cli import domain_dns, execute

class FakeResponse:
    def __init__(self, data): self.data = json.dumps(data).encode()
    def __enter__(self): return io.BytesIO(self.data)
    def __exit__(self,*args): return False

class NETSPECTERTests(unittest.TestCase):
    def test_records_without_web_address(self):
        def response(req, timeout=5):
            url=req.full_url
            typ=int(url.split('type=')[-1])
            answers={15:[{'type':15,'data':'10 mail.example.org.'}],2:[{'type':2,'data':'ns.example.org.'}],16:[{'type':16,'data':'"v=spf1 -all"'}]}
            return FakeResponse({'Status':0,'Answer':answers.get(typ,[])})
        with patch('blackthorn.cli.urllib.request.urlopen',side_effect=response):
            value=domain_dns('example.org')
        self.assertEqual(value['public_addresses'],[])
        self.assertEqual(value['status'],'records found')
        self.assertTrue(value['records']['MX'])
        self.assertTrue(value['records']['NS'])
    def test_dns_failure_is_not_fatal(self):
        with patch('blackthorn.cli.urllib.request.urlopen',side_effect=OSError('offline')):
            value=domain_dns('jedisec.com')
        self.assertEqual(value['status'],'lookup incomplete')
        self.assertIn('A',value['resolver_errors'])
    def test_opt_in_required(self):
        self.assertEqual(execute(5,'jedisec.com',live=False)['status'],'network not used')
    def test_invalid_domain(self):
        with self.assertRaises(ValueError): domain_dns('not a domain')
if __name__=='__main__': unittest.main()
