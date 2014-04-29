"""
These tests verify syncback of the sendmail actions (send, reply) -
they use a real Gmail test account and verify that the sent email message
is present in both the Inbox and Sent Mail folders.

They do not verify the local data store, see tests/imap/test_sendmail.py or
reconciliation on a subsequent sync, see
tests/imap/network/test_sendmail_reconciliation.py

"""
import uuid

from pytest import fixture

from tests.util.crispin import crispin_client
from tests.util.api import api_client
from tests.util.mailsync import sync_client

USER_ID = 1
ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 6
THREAD_TOPIC = 'Golden Gate Park next Sat'


@fixture(scope='function')
def message(db, config):
    from inbox.server.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    to = u'"\u2605The red-haired mermaid\u2605" <{0}>'.\
        format(account.email_address)
    subject = 'Wakeup' + str(uuid.uuid4().hex)
    body = '<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>'

    return (to, subject, body)


def test_send_syncback(db, config, message):
    from inbox.server.sendmail.base import send, recipients
    from inbox.server.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    to, subject, body = message
    attachments = None
    cc = 'ben.bitdiddle1861@gmail.com'
    bcc = None

    send(account, recipients(to, cc, bcc), subject, body, attachments)

    client = crispin_client(account.id, account.provider)
    with client.pool.get() as c:
        # Ensure the sent email message is present in the test account,
        # in both the Inbox and Sent folders:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(subject)]

        c.select_folder(account.inbox_folder_name, None)
        inbox_uids = c.search(criteria)
        assert inbox_uids, 'Message missing from Inbox'

        #c.delete_messages(inbox_uids)

        c.select_folder(account.sent_folder_name, None)
        sent_uids = c.search(criteria)
        assert sent_uids, 'Message missing from Sent'

        #c.delete_messages(sent_uids)


def test_reply_syncback(db, config, message, sync_client):
    from inbox.server.sendmail.base import reply, recipients
    from inbox.server.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    to, subject, body = message
    attachments = None
    cc = 'ben.bitdiddle1861@gmail.com'
    bcc = None

    reply(account, THREAD_ID, recipients(to, cc, bcc), subject, body,
          attachments)

    client = crispin_client(account.id, account.provider)
    with client.pool.get() as c:
        # Ensure the sent email message is present in the test account,
        # in both the Inbox and Sent folders:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(THREAD_TOPIC)]

        c.select_folder(account.inbox_folder_name, None)
        inbox_uids = c.search(criteria)
        assert inbox_uids > 1, 'Reply missing from Inbox'

        # TODO[k]: Don't delete original
        #c.delete_messages(inbox_uids)

        c.select_folder(account.sent_folder_name, None)
        sent_uids = c.search(criteria)
        assert sent_uids, 'Message missing from Sent'

        #c.delete_messages(sent_uids)
