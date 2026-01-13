from datetime import datetime

from src.forensicWace_SE.extractionAndroid import ExecuteQuery
from src.forensicWace_SE.repository.msgstore_db import SQLiteDB
from src.forensicWace_SE.utils import map_message_types


def getContacts(dbpath: str, filter: str):
    #dbpath=device_extractions_Android/Estrazione_1/msgstore.db
    db = SQLiteDB(dbpath)
    db.connect()
    #res = db.execute_query("SELECT * FROM jid WHERE user = 393801894951")
    query = "SELECT DISTINCT user FROM jid"
    if filter:
        query = f'SELECT DISTINCT user FROM jid where user LIKE "{filter}"'

    res = db.execute_query(query)
    return res

#TODO - Not working at this moment
def getBlockedContacts(dbpath: str, filter: str):
    #WhatsApp adds a record to the table “wa_block_list” of the contact database “wa.db”. This table (depicted in Figure 12) contains one field called "jid" that stores the ID (phone number) of the blocked contacts.
    db = SQLiteDB(dbpath)
    db.connect()
    #res = db.execute_query("SELECT * FROM jid WHERE user = 393801894951")
    query = "SELECT DISTINCT user FROM jid"
    if filter:
        query = f'SELECT DISTINCT user FROM jid where user LIKE "{filter}"'

    res = db.execute_query(query)
    return res


def getChat(dbpath: str, type: str, filter: str):
    #db = SQLiteDB(dbpath)
    #db.connect()
    query = "SELECT _id, raw_string_jid as PhoneNumber,subject FROM chat_view"
    like = '%'
    if filter:
        like = filter
    if type == 'contact':
        query = f'SELECT _id, raw_string_jid,subject FROM chat_view WHERE raw_string_jid LIKE "{like}@s.whatsapp.net"'
    if type == 'group':
        query = f'SELECT _id, raw_string_jid,subject FROM chat_view WHERE subject LIKE "{like}"'

    res = ExecuteQuery(dbpath,query)
    #res = db.execute_query(query)
    print(res)
    return res


def getGPSPositionsMessages(dbpath: str):
    db = SQLiteDB(dbpath)
    db.connect()
    query = 'SELECT* FROM message_location'


    res = db.execute_query(query)
    print(res)
    return res


'''
date_to: Optional[datetime] = Query(None, description="Date to filter messages to"),
date_from: Optional[datetime] = Query(None, description="Date to filter messages from"),
received: Optional[int] = Query(None, description="Include received messages (0 or 1)"),
sent: Optional[int] = Query(None, description="Include sent messages (0 or 1)"),
contacts: Optional[List[str]] = Query(None, description="List of contacts to filter messages for"),
groups: Optional[List[str]] = Query(None, description="List of groups to filter messages for"),
msg_type: Optional[List[int]] = Query(None, description="List of types to filter messages for"),
'''

def getMessagesDB(dbpath: str, date_from, date_to, received, sent, contacts, groups, msg_type):
    db = SQLiteDB(dbpath)
    db.connect()
    contact_map = 0
    if contacts:
        # Costruisci la query SQL dinamicamente in modo sicuro
        query = "SELECT chat_view._id, raw_string, user FROM jid inner join chat_view on jid._id = chat_view.jid_row_id WHERE " + " OR ".join(
            [f"user = ?" for _ in contacts])
        query_params = contacts

        # Log della query e dei parametri
        print(f"Query: {query}")
        print(f"Query Params: {query_params}")

        # Esegui la query usando sqlite3
        cursor = db.connection.cursor()
        cursor.execute(query, query_params)
        # Inizializza la mappa per i risultati
        contact_map = {row[0]: row[2] for row in cursor.fetchall()}
        chat_id_contacts = list(contact_map.keys())

    chat_id_map = 0
    if groups:
        # Costruisci la query SQL dinamicamente in modo sicuro
        query = "SELECT _id, jid_row_id,subject FROM chat_view WHERE " + " OR ".join(
            [f"subject = ?" for _ in groups])
        query_params = groups

        # Log della query e dei parametri
        print(f"Query: {query}")
        print(f"Query Params: {query_params}")

        # Esegui la query usando sqlite3
        cursor = db.connection.cursor()
        cursor.execute(query, query_params)
        chat_id_map = {row[0]: row[2] for row in cursor.fetchall()}
        chat_id_groups = list(chat_id_map.keys())

    #recuperati i chatid procedere a compilare la query con i filtri
    #step2 filtrare messages chat_id, range date, from_me (sent, received)

    if contacts is not None and groups is not None:
        chat_ids = chat_id_contacts + chat_id_groups
    if contacts is not None and groups is None:
        chat_ids = chat_id_contacts
    if contacts is None and groups is not None:
        chat_ids = chat_id_groups

    query_chat_filtered = "SELECT _id, chat_row_id,from_me, timestamp, message_type, text_data FROM message WHERE " + "(" + " OR ".join(
        [f"chat_row_id = {chat_id}" for chat_id in chat_ids]) + ")"

    if date_to is not None and date_from is not None:
        date_filter = f' AND timestamp >= {datetime.timestamp(date_from) * 1000} and timestamp <= {datetime.timestamp(date_to) * 1000} '
        query_chat_filtered += date_filter

    if received:
        if sent:
            #do nothing, chat all
            pass
        else:
            from_me_filter = f' AND from_me = 0'
            query_chat_filtered += from_me_filter
    else:
        from_me_filter = f' AND from_me = 1'
        query_chat_filtered += from_me_filter

    #msg types:
    # when 0 then 'text'
    # when 1 - 42 then 'image'
    # when 2 then 'audio'
    # when 3 - 43 then 'video'
    # when 13 then 'gif'
    # when 5 then 'location'
    # when 6 then 'groupEvent'
    # when 7 then 'url'
    # when 9 then 'file'

    msg_type=  map_message_types(msg_type) #converto da testuali a numerici in base ad un mapping definito nel metodo
    if msg_type:
        msg_type_filter = " AND (" + " OR ".join(
            [f"message_type = {type_m}" for type_m in msg_type]) + ")"

        query_chat_filtered += msg_type_filter

    query_chat_filtered += " ORDER BY chat_row_id, timestamp "

    print(f"Query: {query_chat_filtered}")
    res = db.execute_query(query_chat_filtered)
    # Lista per mantenere i risultati con l'elemento aggiuntivo
    res_with_extra = []

    # Itera sulla lista res
    for item in res:
        # Estrai i primi sei elementi
        _id, chat_row_id, from_me, timestamp, message_type, text_data = item
        file_res = db.execute_query(f'Select message_row_id, file_path, file_size, media_caption, mime_type FROM message_media Where message_row_id == {_id}')
        if len(file_res) > 0:
            _, file_path, file_size, media_caption,mime_type = file_res[0]
        # Cerca il valore aggiuntivo nella mappa basato sul numero
        if contact_map:
            contact_name = contact_map.get(chat_row_id, None)
            if contact_name:
                if len(file_res) > 0:
                    res_with_extra.append((contact_name, _id, chat_row_id, from_me, timestamp, message_type, text_data, file_path,file_size,media_caption, mime_type))
                else:
                    res_with_extra.append((contact_name, _id, chat_row_id, from_me, timestamp, message_type, text_data, None, None,None,None))

        if chat_id_map:
            group_name = chat_id_map.get(chat_row_id, None)
            if group_name:
                if len(file_res) > 0:
                    res_with_extra.append((group_name, _id, chat_row_id, from_me, timestamp, message_type, text_data, file_path,file_size,media_caption, mime_type))
                else:
                    res_with_extra.append((group_name, _id, chat_row_id, from_me, timestamp, message_type, text_data, None, None, None, None))
    return res_with_extra
