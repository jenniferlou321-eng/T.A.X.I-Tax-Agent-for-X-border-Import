# SDST Vendor ID Application — Email Template

## When to send

Before submitting CT/PAYE/SDLT in production through GovTalk XML, you need a **Vendor ID** issued by HMRC's Software Developer Support Team (SDST).

## Email template (English)

```
To:      sdsteam@hmrc.gov.uk
CC:      (your accountant / compliance officer)
Subject: Vendor ID Application — T.A.X.I. Cross-Border Tax Filing Tool

Dear SDST,

We are developing an internal software tool, T.A.X.I. (Tax Agent for
X-border & Import), to automate cross-border UK tax filing for our
multi-entity group. We would like to apply for a Vendor ID to access
the HMRC Transaction Engine (GovTalk XML) for the following
endpoints:

  - Corporation Tax:     HMRC-CT-CT600       (CT600)
  - PAYE/RTI:            HMRC-PAYE-RTI-FPS   (FPS)
  - PAYE/RTI:            HMRC-PAYE-RTI-EPS   (EPS)
  - PAYE/RTI:            HMRC-PAYE-RTI-EYU   (EYU)
  - Stamp Duty Land Tax: HMRC-SDLT-RETURN    (SDLT)

We have a Developer Hub account for the REST MTD APIs
(VAT / Self Assessment), and have completed the OAuth flow with the
sandbox. We are now extending the tool to support the legacy
GovTalk XML submission channel.

Use case:
- Single corporate group, single software tool (not commercial)
- Filing for ~5 UK entities (1 parent + 4 subsidiaries)
- Annual volume: ~12 CT600 + ~120 FPS + ~12 EPS + ~6 SDLT
- Production endpoints: Government Gateway user credentials (not
  Vendor ID) will be used at filing time; the Vendor ID is needed
  for development and test access to the External Test Service (ETS).

Technical readiness:
- CRC32 IRmark implementation completed and verified
- Envelope building (GovTalkMessage) implemented
- Async submit + poll pattern implemented
- CT600 / FPS / EPS / EYU / SDLT body builders implemented in Python
- 230+ unit tests passing

We are requesting:
1. Vendor ID
2. Test vendor password
3. Technical packs (XSD schemas) for the 5 message classes listed above
4. Test scenarios and acceptance criteria for ETS

We are happy to:
- Demonstrate the software on a video call before recognition
- Provide test submissions from the ETS environment
- Sign any non-disclosure agreement required

Please let us know what additional information you need.

Best regards,
[Your name]
[Your role]
[Company name]
[Email]
[Phone]
```

## After you get the Vendor ID

1. Add to `.env`:
   ```
   HMRC_VENDOR_ID=<your_vendor_id>
   HMRC_VENDOR_PASSWORD=<your_vendor_password>
   ```

2. Test the connection:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.')
   from backend.channels.govtalk import GovTalkClient
   c = GovTalkClient(vendor_id='<ID>', vendor_password='<PASS>', gateway_test=True)
   import asyncio
   r = asyncio.run(c.submit('HMRC-CT-CT600', '<IRenvelope/>'))
   print('✅ Connected:', r['correlation_id'])
   "
   ```

3. Once ETS testing passes, apply for **recognition** (~10 business days)

## Reference

- Register as a software developer: https://www.gov.uk/government/collections/register-as-a-software-developer
- Basic guide for XML software developers: https://www.gov.uk/guidance/basic-guide-for-xml-software-developers
- IRmark technical pack: https://www.gov.uk/government/collections/hmrcirmark-support-for-software-developers
