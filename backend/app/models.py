from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Doctor(Base):
    __tablename__ = "doctors"
    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String, nullable=False)
    specialization   = Column(String, index=True, nullable=False)
    hospital         = Column(String, nullable=False)
    location         = Column(String, nullable=False, index=True)
    experience_years = Column(Integer, default=0)
    rating           = Column(Float, default=4.0)
    available_slots  = Column(Text, default="")  # comma-separated


class Patient(Base):
    __tablename__ = "patients"
    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String, nullable=False)
    age          = Column(Integer, nullable=True)
    gender       = Column(String, nullable=True)
    phone        = Column(String, nullable=True)
    appointments = relationship("Appointment", back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"
    id         = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id  = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slot       = Column(String, nullable=False)
    status     = Column(String, default="booked")
    created_at = Column(DateTime, default=datetime.utcnow)
    patient    = relationship("Patient", back_populates="appointments")
    doctor     = relationship("Doctor")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id           = Column(Integer, primary_key=True, index=True)
    patient_id   = Column(Integer, nullable=True)
    user_message = Column(Text, nullable=False)
    ai_response  = Column(Text, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)


class ReportUpload(Base):
    __tablename__ = "report_uploads"
    id             = Column(Integer, primary_key=True, index=True)
    patient_name   = Column(String, nullable=True)
    raw_text       = Column(Text, nullable=False)
    hypothesis     = Column(Text, nullable=True)
    specialization = Column(String, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
