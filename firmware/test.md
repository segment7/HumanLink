input:
```
{"cmd":"auth","h_doc":"1122334455667788112233445566778811223344556677881122334455667788","nonce":"0102030405060708","display":{"title":"Test Authorization"}}
```

output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Action : Test Authorization
[HumanLink] Risk   : unknown
[HumanLink] Place finger on sensor to authorize...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Fingerprint matched: slot=1 score=104
{"status":"ok","protocol":"0.3","matched_id":1,"score":104,"sensor_serial":"5555aaaa5555aaaa5043344b303531333433423453594e4f3039303241ffffff","nonce":"0102030405060708","signed_hash":"096ad83e66477d5c7a2fc0976755576f3fc042ed1b97b890a6dd34cd6933c080","sig":"WjrujyNW9BVJwWyfGRcqBLLemqwLqVyiV8akk9g41zerSioep1ya0pjGUm+80EsFziXZaVMdXIED4D3N1HjpoA==","pubkey":"K5cNFviOdfA26sjuXMvS863l9xQK7xJVEQXomw4F2s08hX5sJJ+DbSf61Kk5i8semQfKEkPX5hm48fq0ub3qog=="}
[HumanLink] Authorization complete.
```

```
 Output on error:
 {"status":"err","code":2,"msg":"no match"}
```