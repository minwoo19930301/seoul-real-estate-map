import hashlib
import json
import unittest
from unittest.mock import patch
from scripts.collect_proptech_brightdata import extract_kb, sql, TRANSPORT


def sample():
    data = {'complexId': '22859', 'data': {'detail': {'단지기본일련번호': 22859,
        '단지명': '테스트 단지', '총주차대수': 0, '승강기유무': None,
        '소유자이름': 'DO_NOT_STORE'}, 'typeList': [{'단지기본일련번호': 22859,
        '면적일련번호': 1, '연평균총관리비': 180339, '방수': 3, '욕실수': 2}],
        'talkInfo': {'user': 'DO_NOT_STORE'}, 'loanInfo': {'LTV': 'DO_NOT_STORE'}}}
    stream = '5:' + json.dumps(data, ensure_ascii=False) + '\n'
    raw = ('<script>self.__next_f.push(' + json.dumps([1, stream]) + ')</script>').encode()
    receipt = {'url': 'https://kbland.kr/se/c/22859', 'transport': TRANSPORT,
               'httpStatus': 200, 'sha256': hashlib.sha256(raw).hexdigest()}
    return raw, receipt


class Extraction(unittest.TestCase):
    def test_provenance_required(self):
        raw, receipt = sample()
        for change in [{'transport': 'direct'}, {'sha256': 'bad'}, {'httpStatus': 403},
                       {'url': 'https://kbland.kr/se/c/1'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                extract_kb(raw, {**receipt, **change})
    def test_no_private_fields_and_no_missing_inference(self):
        raw, receipt = sample()
        data = extract_kb(raw, receipt)
        self.assertNotIn('DO_NOT_STORE', json.dumps(data))
        fields = {r['field']: r for r in data['facts']}
        self.assertEqual(fields['총주차대수']['value'], 0)
        self.assertEqual(fields['총주차대수']['status'], 'observed')
        self.assertEqual(fields['승강기유무']['status'], 'not_observed')
        self.assertEqual(fields['연평균총관리비']['value'], 180339)
        self.assertNotIn('공용관리비', fields)
    def test_shell_is_not_data(self):
        _, receipt = sample()
        raw = b'<html>Login required</html>'
        receipt['sha256'] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            extract_kb(raw, receipt)


class Transactions(unittest.TestCase):
    def test_write_error_rolls_back_without_commit(self):
        replies = [{'baton': 'opaque', 'results': [{'type': 'error'}]}, {'results': []}]
        with patch('scripts.collect_proptech_brightdata.http_json', side_effect=replies) as request:
            with self.assertRaises(RuntimeError):
                sql('test.turso.io', 'secret', [('BEGIN', []), ('INSERT', []), ('COMMIT', [])])
            body = request.call_args.args[2]
            self.assertEqual(body['baton'], 'opaque')
            self.assertEqual(body['requests'][0]['stmt']['sql'], 'ROLLBACK')
    def test_commit_follows_checked_response(self):
        ok = {'type': 'ok', 'response': {'type': 'execute', 'result': {'rows': []}}}
        with patch('scripts.collect_proptech_brightdata.http_json', side_effect=[
            {'baton': 'opaque', 'results': [ok]}, {'results': [ok]}]) as request:
            sql('test.turso.io', 'secret', [('BEGIN', []), ('COMMIT', [])])
            self.assertEqual(request.call_args.args[2]['requests'][0]['stmt']['sql'], 'COMMIT')

if __name__ == '__main__':
    unittest.main()
