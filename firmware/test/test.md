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


log:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Firmware v0.3 starting
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Initializing JM-101 fingerprint sensor...
[HumanLink] JM-101 pins: RX=GPIO16, TX=GPIO17
[JM101] Probing fingerprint sensor...
[JM101] Probe attempt 1/3
[JM101] Sensor responded successfully, 1 templates enrolled
[HumanLink] JM-101 sensor connected successfully
[HumanLink] Initializing ATECC608A secure element...
[HumanLink] I2C pins: SDA=GPIO21, SCL=GPIO22
[  1605][I][esp32-hal-i2c.c:75] i2cInit(): Initialising I2C Master: sda=21 scl=22 freq=100000
[SE] Chip lock status: LOCKED
[SE] Chip is already locked, checking existing key...
[SE] Existing key in slot 0 is accessible
[SE] ATECC608A ready
[HumanLink] ATECC608A connected successfully
[HumanLink] Device already initialized
[HumanLink] Device DID: did:key:zciqcxfync34i45pqg3vmr3s4zpjphlpf64kav3yskuiql2e3byc5vtj4qv7gyje7qnwsp6wuve4yxsy6ted4uesd27tbtohr7k2ltppkui
{"event":"ready","protocol":"0.3","device_did":"did:key:zciqcxfync34i45pqg3vmr3s4zpjphlpf64kav3yskuiql2e3byc5vtj4qv7gyje7qnwsp6wuve4yxsy6ted4uesd27tbtohr7k2ltppkui","enrolled":1}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Action : Unknown action
[HumanLink] Risk   : unknown
[HumanLink] Place finger on sensor to authorize...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{"status":"err","code":2,"msg":"fingerprint no match"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Action : Unknown action
[HumanLink] Risk   : unknown
[HumanLink] Place finger on sensor to authorize...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{"status":"err","code":2,"msg":"fingerprint no match"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Action : Unknown action
[HumanLink] Risk   : unknown
[HumanLink] Place finger on sensor to authorize...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HumanLink] Fingerprint matched: slot=1 score=94
{"status":"ok","protocol":"0.3","matched_id":1,"score":94,"sensor_serial":"5555aaaa5555aaaa5043344b303531333433423453594e4f3039303241ffffff","nonce":"0102030405060708","signed_hash":"ec638a8f84efb41fde81ba3e60d742b7a90e803efb4fa5be79ec1874aa121467","sig":"XrwsSZauha1IkZiOYjhwmqbyELIn3dya4AToCXN/xt2xzLJpqeFo0m2j7GQ0sdhSM1fwGQ3IYfDfh+hAOna1rQ==","pubkey":"K5cNFviOdfA26sjuXMvS863l9xQK7xJVEQXomw4F2s08hX5sJJ+DbSf61Kk5i8semQfKEkPX5hm48fq0ub3qog=="}
[HumanLink] Authorization complete.
```