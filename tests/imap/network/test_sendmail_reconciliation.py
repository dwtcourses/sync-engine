"""
These tests verify that messages sent from Inbox are correctly reconciled
with the `Sent Mail` messages synced from the remote backend during a
subsequent sync - they use the sendmail API calls and then run a sync on the
account to do so.

They do not verify the local data store, see tests/imap/test_sendmail.py or
syncback to the remote backend, tests/imap/network/test_sendmail_syncback.py

"""
import uuid

from pytest import fixture
from gevent import Greenlet

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


def test_send_reconcile(db, config, message, api_client, sync_client):
    from inbox.server.models.tables.base import Message, SpoolMessage

    to, subject, body = message
    attachment = None
    cc = 'ben.bitdiddle1861@gmail.com'
    bcc = None

    # Create email message, store a local copy + send it:
    api_client.send_new(USER_ID, NAMESPACE_ID, to, subject, body, attachment,
                        cc, bcc)

    # Sync to verify reconciliation:
    synclet = Greenlet(sync_client.start_sync, ACCOUNT_ID)
    synclet.start()

    Greenlet.join(synclet, timeout=60)

    sync_client.stop_sync(ACCOUNT_ID)

    spool_messages = db.session.query(SpoolMessage).\
        filter_by(subject=subject).all()
    assert len(spool_messages) == 1, 'spool message missing'

    resolved_message_id = spool_messages[0].resolved_message_id
    assert resolved_message_id, 'spool message not reconciled'

    inbox_uid = spool_messages[0].inbox_uid
    thread_id = spool_messages[0].thread_id

    reconciled_message = db.session.query(Message).get(resolved_message_id)
    assert reconciled_message.inbox_uid == inbox_uid,\
        'spool message, reconciled message have different inbox_uids'

    assert reconciled_message.thread_id == thread_id,\
        'spool message, reconciled message have different thread_ids'

    # Delete emails
    #_delete_emails(db, ACCOUNT_ID, subject)


def test_reply_reconcile(db, config, message, api_client, sync_client):
    from inbox.server.models.tables.base import Message, SpoolMessage

    to, subject, body = message
    attachment = None
    cc = 'ben.bitdiddle1861@gmail.com'
    bcc = None

    # Create email message, store a local copy + send it:
    api_client.send_reply(USER_ID, NAMESPACE_ID, THREAD_ID, to, subject, body,
                          attachment, cc, bcc)

    # Sync to verify reconciliation:
    synclet = Greenlet(sync_client.start_sync, ACCOUNT_ID)
    synclet.start()

    Greenlet.join(synclet, timeout=60)

    sync_client.stop_sync(ACCOUNT_ID)

    spool_messages = db.session.query(SpoolMessage).\
        filter_by(subject=THREAD_TOPIC).all()
    assert len(spool_messages) == 1, 'spool message missing'

    resolved_message_id = spool_messages[0].resolved_message_id
    assert resolved_message_id, 'spool message not reconciled'

    inbox_uid = spool_messages[0].inbox_uid
    thread_id = spool_messages[0].thread_id
    g_thrid = spool_messages[0].g_thrid

    reconciled_message = db.session.query(Message).get(resolved_message_id)
    assert reconciled_message.inbox_uid == inbox_uid,\
        'spool message, reconciled message have different inbox_uids'

    assert reconciled_message.thread_id == thread_id,\
        'spool message, reconciled message have different thread_ids'

    assert reconciled_message.g_thrid == g_thrid,\
        'spool message, reconciled message have different g_thrids'

    # Delete emails
    # TODO[k]: Don't delete original
    #_delete_emails(db, ACCOUNT_ID, THREAD_TOPIC)


def _delete_emails(db, account_id, subject):
    from inbox.server.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(account_id)

    client = crispin_client(account.id, account.provider)
    with client.pool.get() as c:
        # Ensure the sent email message is present in the test account,
        # in both the Inbox and Sent folders:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(subject)]

        c.select_folder(account.inbox_folder_name, None)
        inbox_uids = c.search(criteria)
        c.delete_messages(inbox_uids)

        c.select_folder(account.sent_folder_name, None)
        sent_uids = c.search(criteria)
        c.delete_messages(sent_uids)
