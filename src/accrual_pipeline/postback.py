"""Mock SAP S/4 Journal Entry Post.

In dev: logs the intended SOAP envelope at INFO with a clear "WOULD CALL"
prefix so it's obvious nothing was sent. A CPI port replaces this with a
real SOAP adapter call to S/4's Journal Entry Post service.

The envelope is synthesized here rather than persisted — if you want to
diff envelopes across runs, scrape them from the log stream.
"""
from __future__ import annotations

from datetime import datetime, timezone
from xml.sax.saxutils import escape

import structlog

log = structlog.get_logger(__name__)

_SOAP_TEMPLATE = """\
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:jep="http://sap.com/xi/A1S/JournalEntryPost">
  <soapenv:Header/>
  <soapenv:Body>
    <jep:JournalEntryPostRequest>
      <MessageHeader>
        <RunID>{run_id}</RunID>
        <Timestamp>{timestamp}</Timestamp>
      </MessageHeader>
      <JournalEntry>
        <AccrualID>{accrual_id}</AccrualID>
        <ApprovalNotes>{notes}</ApprovalNotes>
      </JournalEntry>
    </jep:JournalEntryPostRequest>
  </soapenv:Body>
</soapenv:Envelope>\
"""


async def post_journal_entry(
    *,
    run_id: str,
    accrual_id: str,
    notes: str,
) -> None:
    """Simulate posting an approved accrual back to S/4 — logs only.

    Never makes a real network call. Safe to run in any environment.
    """
    envelope = _SOAP_TEMPLATE.format(
        run_id=escape(run_id),
        timestamp=datetime.now(timezone.utc).isoformat(),
        accrual_id=escape(accrual_id),
        notes=escape(notes),
    )
    log.info(
        "postback.would_call_s4",
        run_id=run_id,
        accrual_id=accrual_id,
        envelope=envelope,
    )
