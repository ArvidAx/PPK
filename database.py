"""
Database module for the Swedish Protein Per Krona (PPK) application.
This module defines the SQLAlchemy schema, manages database initialization,
and handles data queries and mock data seeding.
"""

import os
from datetime import datetime
import pandas as pd
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Define database location relative to this file
DATABASE_FILE = "ppk_database.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Initialize declarative base
Base = declarative_base()


class Store(Base):
    """
    Represents a grocery store in the database.
    """
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)

    # Relationships
    prices = relationship("Price", back_populates="store", cascade="all, delete-orphan")


class Product(Base):
    """
    Represents a grocery product and its nutritional values.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ean = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=False)
    protein_per_100g = Column(Float, nullable=False)
    fat_per_100g = Column(Float, nullable=False)
    carbs_per_100g = Column(Float, nullable=False)
    calories_100g = Column(Integer, nullable=False)
    nova_group = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)

    # Relationships
    prices = relationship("Price", back_populates="product", cascade="all, delete-orphan")


class Price(Base):
    """
    Represents a product's price and package details at a specific store.
    """
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    price_sek = Column(Float, nullable=False)
    package_size_grams = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="prices")
    store = relationship("Store", back_populates="prices")


# Create engine and session factory
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initializes the database schema and ensures stores are created.
    Uses robust exception handling to ensure database safety.
    """
    try:
        # Create all tables if they do not exist
        Base.metadata.create_all(bind=engine)
        
        session = SessionLocal()
        try:
            # Check if stores exist; if not, create the standard stores
            if session.query(Store).count() == 0:
                willys = Store(name="Willys")
                hemkop = Store(name="Hemköp")
                lidl = Store(name="Lidl")
                session.add_all([willys, hemkop, lidl])
                session.commit()
                print("Standardbutiker (Willys, Hemköp, Lidl) skapade i tom databas.")
        finally:
            session.close()
    except Exception as e:
        print(f"Error initializing the database: {e}")
        raise e


def seed_database(session):
    """
    Seeds the database with stores and the 10 Swedish mock grocery products
    along with highly realistic and competitive prices across stores.
    """
    # 1. Add stores
    willys = Store(name="Willys")
    hemkop = Store(name="Hemköp")
    lidl = Store(name="Lidl")
    
    session.add_all([willys, hemkop, lidl])
    session.flush()  # Generate IDs for stores

    # 2. Add products
    products_data = [
        {
            "ean": "7310865004734",
            "name": "Keso Naturell",
            "brand": "Arla",
            "protein_per_100g": 12.0,
            "fat_per_100g": 4.0,
            "carbs_per_100g": 2.0,
            "calories_100g": 93,
            "nova_group": 3,
            "category": "Mejeri",
            # Prices: Arla is a national brand, Hemköp is slightly more expensive, Willys/Lidl competitive
            "prices": [
                {"store_id": willys.id, "price_sek": 32.90, "package_size_grams": 500.0},
                {"store_id": hemkop.id, "price_sek": 35.90, "package_size_grams": 500.0},
                {"store_id": lidl.id, "price_sek": 33.50, "package_size_grams": 500.0}
            ]
        },
        {
            "ean": "7392672001234",
            "name": "Kvarg Naturell",
            "brand": "Milbona",
            "protein_per_100g": 11.5,
            "fat_per_100g": 0.2,
            "carbs_per_100g": 3.0,
            "calories_100g": 60,
            "nova_group": 1,
            "category": "Mejeri",
            # Lidl Private Brand: Highly competitive price at Lidl, slightly higher simulated elsewhere
            "prices": [
                {"store_id": willys.id, "price_sek": 19.90, "package_size_grams": 500.0},
                {"store_id": hemkop.id, "price_sek": 21.90, "package_size_grams": 500.0},
                {"store_id": lidl.id, "price_sek": 16.90, "package_size_grams": 500.0}
            ]
        },
        {
            "ean": "7310340012543",
            "name": "Nötfärs 10%",
            "brand": "Scan",
            "protein_per_100g": 20.0,
            "fat_per_100g": 10.0,
            "carbs_per_100g": 0.0,
            "calories_100g": 170,
            "nova_group": 1,
            "category": "Kött & Fågel",
            # Scan Nötfärs: Premium meat brand, Willys cheapest, Hemköp highest
            "prices": [
                {"store_id": willys.id, "price_sek": 69.95, "package_size_grams": 500.0},
                {"store_id": hemkop.id, "price_sek": 74.95, "package_size_grams": 500.0},
                {"store_id": lidl.id, "price_sek": 71.90, "package_size_grams": 500.0}
            ]
        },
        {
            "ean": "7310532104562",
            "name": "Kycklingfilé",
            "brand": "Gyllda",
            "protein_per_100g": 22.0,
            "fat_per_100g": 1.2,
            "carbs_per_100g": 0.0,
            "calories_100g": 105,
            "nova_group": 1,
            "category": "Kött & Fågel",
            # Lidl Private Brand: Massive discount at Lidl
            "prices": [
                {"store_id": willys.id, "price_sek": 99.90, "package_size_grams": 1000.0},
                {"store_id": hemkop.id, "price_sek": 109.90, "package_size_grams": 1000.0},
                {"store_id": lidl.id, "price_sek": 89.90, "package_size_grams": 1000.0}
            ]
        },
        {
            "ean": "7310130005324",
            "name": "Havregryn",
            "brand": "AXA",
            "protein_per_100g": 13.0,
            "fat_per_100g": 7.0,
            "carbs_per_100g": 58.0,
            "calories_100g": 370,
            "nova_group": 1,
            "category": "Spannmål & Kolhydrater",
            # National grain staple
            "prices": [
                {"store_id": willys.id, "price_sek": 24.90, "package_size_grams": 1500.0},
                {"store_id": hemkop.id, "price_sek": 27.90, "package_size_grams": 1500.0},
                {"store_id": lidl.id, "price_sek": 25.50, "package_size_grams": 1500.0}
            ]
        },
        {
            "ean": "8013312345678",
            "name": "Fullkornspasta",
            "brand": "Barilla",
            "protein_per_100g": 12.5,
            "fat_per_100g": 2.0,
            "carbs_per_100g": 65.0,
            "calories_100g": 350,
            "nova_group": 1,
            "category": "Spannmål & Kolhydrater",
            # Barilla Import Pasta
            "prices": [
                {"store_id": willys.id, "price_sek": 18.90, "package_size_grams": 500.0},
                {"store_id": hemkop.id, "price_sek": 21.90, "package_size_grams": 500.0},
                {"store_id": lidl.id, "price_sek": 19.50, "package_size_grams": 500.0}
            ]
        },
        {
            "ean": "7300156789123",
            "name": "Tonfisk i Vatten",
            "brand": "Eldorado",
            "protein_per_100g": 24.0,
            "fat_per_100g": 1.0,
            "carbs_per_100g": 0.0,
            "calories_100g": 110,
            "nova_group": 3,
            "category": "Fisk & Skaldjur",
            # Eldorado: Budget private label of Axfood. Willys is extremely cheap, Hemköp moderate, Lidl competitive
            "prices": [
                {"store_id": willys.id, "price_sek": 11.90, "package_size_grams": 185.0},
                {"store_id": hemkop.id, "price_sek": 13.90, "package_size_grams": 185.0},
                {"store_id": lidl.id, "price_sek": 12.50, "package_size_grams": 185.0}
            ]
        },
        {
            "ean": "7350012345678",
            "name": "Röda Linser",
            "brand": "GoGreen",
            "protein_per_100g": 24.0,
            "fat_per_100g": 1.5,
            "carbs_per_100g": 50.0,
            "calories_100g": 330,
            "nova_group": 1,
            "category": "Vegetabiliska Proteiner",
            # Vegetarian staple
            "prices": [
                {"store_id": willys.id, "price_sek": 19.90, "package_size_grams": 500.0},
                {"store_id": hemkop.id, "price_sek": 22.90, "package_size_grams": 500.0},
                {"store_id": lidl.id, "price_sek": 20.50, "package_size_grams": 500.0}
            ]
        },
        {
            "ean": "7311234567890",
            "name": "Vegansk Formbar Vegofärs",
            "brand": "Vemondo",
            "protein_per_100g": 16.0,
            "fat_per_100g": 4.0,
            "carbs_per_100g": 2.0,
            "calories_100g": 120,
            "nova_group": 4,
            "category": "Vegetabiliska Proteiner",
            # Vemondo: Lidl's vegan brand
            "prices": [
                {"store_id": willys.id, "price_sek": 39.90, "package_size_grams": 400.0},
                {"store_id": hemkop.id, "price_sek": 42.90, "package_size_grams": 400.0},
                {"store_id": lidl.id, "price_sek": 34.90, "package_size_grams": 400.0}
            ]
        },
        {
            "ean": "7300123456789",
            "name": "Svensk Falukorv",
            "brand": "Matriket",
            "protein_per_100g": 9.0,
            "fat_per_100g": 18.0,
            "carbs_per_100g": 8.0,
            "calories_100g": 230,
            "nova_group": 4,
            "category": "Kött & Fågel",
            # Matriket: Lidl private Swedish brand
            "prices": [
                {"store_id": willys.id, "price_sek": 29.90, "package_size_grams": 800.0},
                {"store_id": hemkop.id, "price_sek": 32.90, "package_size_grams": 800.0},
                {"store_id": lidl.id, "price_sek": 26.90, "package_size_grams": 800.0}
            ]
        }
    ]

    # Save to database
    for item in products_data:
        prod = Product(
            ean=item["ean"],
            name=item["name"],
            brand=item["brand"],
            protein_per_100g=item["protein_per_100g"],
            fat_per_100g=item["fat_per_100g"],
            carbs_per_100g=item["carbs_per_100g"],
            calories_100g=item["calories_100g"],
            nova_group=item["nova_group"],
            category=item["category"]
        )
        session.add(prod)
        session.flush()  # Generate prod.id for price association

        for price_info in item["prices"]:
            price_entry = Price(
                product_id=prod.id,
                store_id=price_info["store_id"],
                price_sek=price_info["price_sek"],
                package_size_grams=price_info["package_size_grams"]
            )
            session.add(price_entry)

    session.commit()


def get_all_products_prices():
    """
    Fetches a joined representation of products, prices, and stores.
    Computes the Protein Per Krona (PPK) directly in SQL:
    PPK = (package_size_grams * protein_per_100g) / (100 * price_sek)
    Returns a Pandas DataFrame formatted for Streamlit consumption.
    """
    try:
        session = SessionLocal()
        
        # SQLAlchemy Query computing PPK directly in SQL using basic mathematical operations
        query = session.query(
            Product.name.label("Produkt"),
            Product.brand.label("Märke"),
            Store.name.label("Butik"),
            Price.price_sek.label("Pris"),
            Price.package_size_grams.label("Storlek (g)"),
            Product.protein_per_100g.label("Protein/100g"),
            Product.nova_group.label("NOVA-Grupp"),
            Product.category.label("Kategori"),
            Product.ean.label("EAN"),
            # Direct SQL computation of PPK: (package_size * protein / 100) / price
            ((Price.package_size_grams * Product.protein_per_100g) / (100.0 * Price.price_sek)).label("PPK")
        ).join(Price, Price.product_id == Product.id)\
         .join(Store, Store.id == Price.store_id)
        
        # Load SQL results directly into a Pandas DataFrame
        df = pd.read_sql(query.statement, session.bind)
        session.close()
        
        # Round the PPK column to two decimal places
        if not df.empty:
            df["PPK"] = df["PPK"].round(2)
            
        return df
    except Exception as e:
        print(f"Error querying database: {e}")
        return pd.DataFrame()
