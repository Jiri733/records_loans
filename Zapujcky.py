import json
import uuid
from datetime import datetime
from abc import ABC, abstractmethod

# --- 1. OOP Třídy a Abstraktní Rozhraní ---

class Item:
    """Reprezentuje předmět(knihu) k zapůjčení."""
    def __init__(self, name: str, inventory_number: str, item_id: str = None):
        self.item_id = item_id if item_id else str(uuid.uuid4())
        self.name = name
        self.inventory_number = inventory_number

    def to_dict(self):
        return self.__dict__

class User:
    """Reprezentuje uživatele/vypůjčitele."""
    def __init__(self, name: str, user_id: str = None):
        self.user_id = user_id if user_id else str(uuid.uuid4())
        self.name = name
    
    def to_dict(self):
        return self.__dict__

class Loan(ABC):
    """
    Abstraktní základní třída pro všechny typy zápůjček.
    """
    def __init__(self, item_id: str, user_id: str, start_time: str, end_time: str, loan_id: str = None):
        self.loan_id = loan_id if loan_id else str(uuid.uuid4())
        self.item_id = item_id
        self.user_id = user_id
        self.start_time = start_time
        self.end_time = end_time

    @abstractmethod
    def get_type(self) -> str:
        """Abstraktní metoda pro identifikaci typu (pro Factory Method)."""
        pass
    
    def to_dict(self):
        """Převede objekt na slovník pro uložení do JSON a explicitně přidá typ zápůjčky."""
        data = self.__dict__.copy()
        data['loan_type'] = self.get_type() # DŮLEŽITÉ: Uloží typ jako řetězec
        return data

# --- Odvozené třídy pro Factory Method ---

class StandardLoan(Loan):
    """Standardní zápůjčka."""
    def get_type(self) -> str:
        return "standard"

class StaffLoan(Loan):
    """Zápůjčka pro zaměstnance s volitelnou poznámkou."""
    def __init__(self, item_id: str, user_id: str, start_time: str, end_time: str, note: str, loan_id: str = None):
        super().__init__(item_id, user_id, start_time, end_time, loan_id)
        self.note = note

    def get_type(self) -> str:
        return "staff"

# --- 2. Návrhový Vzor: Factory Method ---

class LoanFactory:
    """Továrna pro vytváření konkrétních typů objektů Loan (Zápůjček) (Factory Method)."""
    def create_loan(self, loan_type: str, item_id: str, user_id: str, start_time: str, end_time: str, **kwargs) -> Loan:
        
        if loan_type == "standard":
            return StandardLoan(item_id, user_id, start_time, end_time)
        elif loan_type == "staff":
            note = kwargs.get("note", "Není uvedena")
            return StaffLoan(item_id, user_id, start_time, end_time, note)
        else:
            raise ValueError(f"Neznámý typ zápůjčky: {loan_type}")

# --- 3. JSON Správce Dat ---

class JSONManager:
    """Spravuje perzistentní ukládání dat do JSON souboru."""
    def __init__(self, filename="lending_db.json"):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        """Načte data ze souboru JSON (Try/Except pro chyby I/O)."""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault("items", [])
                data.setdefault("users", [])
                data.setdefault("loans", [])
                return data
        except FileNotFoundError:
            return {"items": [], "users": [], "loans": []}
        except json.JSONDecodeError:
            print("Chyba při dekódování JSON souboru. Vytvářím nové prázdné úložiště.")
            return {"items": [], "users": [], "loans": []}

    def _save_data(self):
        """Uloží aktuální data zpět do souboru JSON."""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)

    def get_loans_for_item(self, item_id: str) -> list:
        """Vrátí všechny zápůjčky pro daný předmět."""
        return [loan for loan in self.data["loans"] if loan.get("item_id") == item_id]
        
    def add_data(self, key: str, data_object):
        """Obecná metoda pro přidávání dat (Item, User, Loan)."""
        self.data[key].append(data_object.to_dict())
        self._save_data()

# --- 4. Algoritmus: Detekce Konfliktu ---

def check_for_conflict(item_id: str, new_start_str: str, new_end_str: str, json_manager: JSONManager) -> bool:
    """
    Implementace algoritmu detekce konfliktu (překryvu intervalů).
    Vrací True, pokud konflikt EXISTUJE.
    """
    
    # 1. Validace a převod časů (Try/Except ValueError)
    try:
        new_start = datetime.strptime(new_start_str, '%Y-%m-%d %H:%M')
        new_end = datetime.strptime(new_end_str, '%Y-%m-%d %H:%M')
    except ValueError:
        print("Chyba: Neplatný formát času (očekáváno YYYY-MM-DD HH:MM).")
        return True

    if new_start >= new_end:
        print("Chyba: Začátek musí být dříve než konec.")
        return True

    # 2. Získání existujících zápůjček pro daný Item
    existing_loans = json_manager.get_loans_for_item(item_id)

    # 3. Logika detekce překryvu intervalů
    for loan_data in existing_loans:
        try:
            existing_start = datetime.strptime(loan_data["start_time"], '%Y-%m-%d %H:%M')
            existing_end = datetime.strptime(loan_data["end_time"], '%Y-%m-%d %H:%M')
        except ValueError:
            continue 

        # Podmínka překryvu: A_start < N_end AND N_start < A_end
        if existing_start < new_end and new_start < existing_end:
            print(f"Konflikt nalezen s existující zápůjčkou ID: {loan_data.get('loan_id', 'Neznámé')[:8]}...")
            return True

    print("Konflikt nenalezen. Předmět je v daném intervalu volný.")
    return False

def process_loan(loan_type: str, item_id: str, user_id: str, start_time: str, end_time: str, json_manager: JSONManager, **kwargs) -> bool:
    """Hlavní funkce, která zpracovává novou zápůjčku a vypisuje výsledky."""
    print(f"\n--- Pokus o zápůjčku pro Item ID {item_id[:8]}... ({start_time} - {end_time}) ---")

    # 1. Detekce konfliktu
    if check_for_conflict(item_id, start_time, end_time, json_manager):
        print("Zápůjčka NEBYLA provedena kvůli konfliktu v kalendáři.")
        return False
    
    # 2. Vytvoření objektu pomocí Factory Method
    factory = LoanFactory()
    try:
        new_loan = factory.create_loan(loan_type, item_id, user_id, start_time, end_time, **kwargs)
    except ValueError as e:
        print(f"Chyba Factory: {e}")
        return False

    # 3. Uložení zápůjčky
    json_manager.add_data("loans", new_loan)
    print(f"Zápůjčka typu '{loan_type.upper()}' pro Item ID {item_id[:8]}... úspěšně uložena.")
    return True

# --- 5. Testovací Scénáře ---

if __name__ == "__main__":
    
    print("### Spuštění testovací sady Evidence Zápůjček ###")
    
    db = JSONManager()
    
    # Reset dat pro test (zajištění čistého startu)
    db.data = {"items": [], "users": [], "loans": []}
    db._save_data()
    
    # 1. Inicializace základních dat (User a Item)
    user_a = User(name="Jiri Ryska")
    user_b = User(name="Marie Vagnerova")
    item_book = Item(name="Python kucharka", inventory_number="B101")
    
    db.add_data("users", user_a)
    db.add_data("items", item_book)
    
    ITEM_ID_BOOK = item_book.item_id
    USER_ID_A = user_a.user_id
    USER_ID_B = user_b.user_id

    print(f"\n--- Item ID pro testování: {ITEM_ID_BOOK[:8]}... ---")

    # --- Test 1: Úspěšná referenční zápůjčka (R1: 10:00 - 12:00) ---
    print("\n[TEST 1] Standardní zápůjčka (R1: 10:00 - 12:00) - OČEKÁVÁNO: ÚSPĚCH")
    process_loan(
        "standard", ITEM_ID_BOOK, USER_ID_A, 
        "2026-11-28 10:00", "2026-11-28 12:00", db
    )

    # --- Test 2: Kolize (Překryv: 11:30 - 13:00) ---
    print("\n[TEST 2] Pokus o kolizi (11:30 - 13:00) - OČEKÁVÁNO: KONFLIKT")
    process_loan(
        "standard", ITEM_ID_BOOK, USER_ID_B, 
        "2026-11-28 11:30", "2026-11-28 13:00", db
    )

    # --- Test 3: Úspěšná navazující zápůjčka (12:00 - 14:00) ---
    print("\n[TEST 3] Navazující zápůjčka (R2: 12:00 - 14:00) - OČEKÁVÁNO: ÚSPĚCH")
    process_loan(
        "standard", ITEM_ID_BOOK, USER_ID_A, 
        "2026-11-28 12:00", "2026-11-28 14:00", db
    )

    # --- Test 4: Factory Method a specifický typ zápůjčky (StaffLoan) ---
    print("\n[TEST 4] StaffLoan (15:00 - 16:00) s poznámkou - OČEKÁVÁNO: ÚSPĚCH (Factory)")
    process_loan(
        "staff", ITEM_ID_BOOK, USER_ID_B, 
        "2026-11-28 15:00", "2026-11-28 16:00", db, 
        note="Pro interní školení."
    )
    
    # 4. Závěrečný přehled dat
    print("\n--- KONTROLA ZAPSANYCH ZÁPŮJČEK ---")
    
    loans_data = db.data.get("loans", [])
    if loans_data:
        for loan in loans_data:
            loan_type = loan.get('loan_type', 'Neznámý') 
            print(f"ID: {loan['loan_id'][:8]}..., Typ: {loan_type.upper()}, Od: {loan['start_time']}, Do: {loan['end_time']}")
    else:
        print("Databáze zápůjček je prázdná.")

    print("\n### Testovací sada dokončena. ###")