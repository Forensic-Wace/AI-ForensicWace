from src.forensicWace_SE.repository.database import SessionLocal
from src.forensicWace_SE.repository.models import ProcessStatus

session = SessionLocal

def add_process_status(status):
    session.add(status)
    session.commit()

def get_process_status(process_id):
    return session.query(ProcessStatus).filter_by(process_id=process_id).first()

def update_process_status(process:ProcessStatus, **kwargs):
    status = get_process_status(process.process_id)
    if status:
        for key, value in kwargs.items():
            setattr(status, key, value)
        session.commit()

def delete_process_status(process:ProcessStatus):
    status = get_process_status(process.process_id)
    if status:
        session.delete(status)
        session.commit()

def get_process_status_all():
    return session.query(ProcessStatus).order_by(ProcessStatus.start_time.desc()).all()
