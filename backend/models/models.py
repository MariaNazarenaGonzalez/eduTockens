# TODO: Define SQLAlchemy ORM models for roles, users, products, and purchases.

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    
    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    legajo = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    public_key_pem = Column(Text, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    role = relationship("Role", back_populates="users")
    purchases = relationship("Purchase", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price_points = Column(Integer, nullable=False)
    stock = Column(Integer)  # NULL = unlimited
    active = Column(Boolean, default=True)
    image_data = Column(LargeBinary)  # Product image as binary
    image_mime_type = Column(String(50))  # e.g. image/jpeg
    created_at = Column(DateTime, default=datetime.utcnow)
    
    purchases = relationship("Purchase", back_populates="product")

class Purchase(Base):
    __tablename__ = "purchases"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    points_spent = Column(Integer, nullable=False)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    nct_transaction_id = Column(String(100))  # Reference to blockchain transaction
    
    user = relationship("User", back_populates="purchases")
    product = relationship("Product", back_populates="purchases")
