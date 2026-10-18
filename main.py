from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


APP_DIR = Path(__file__).resolve().parent


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self):
        self.conn.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT DEFAULT '',
            category TEXT DEFAULT '',
            unit TEXT DEFAULT 'قطعة',
            buy_price REAL DEFAULT 0,
            sell_price REAL DEFAULT 0,
            stock REAL DEFAULT 0,
            min_stock REAL DEFAULT 0,
            expiry TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            phone TEXT DEFAULT '',
            balance REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL,
            kind TEXT NOT NULL,
            contact_id INTEGER,
            total REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(contact_id) REFERENCES contacts(id)
        );
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT DEFAULT '');
        """)
        self.conn.commit()

    def scalar(self, sql, args=()):
        row = self.conn.execute(sql, args).fetchone()
        return row[0] if row else 0

    def rows(self, sql, args=()):
        return self.conn.execute(sql, args).fetchall()

    def add_product(self, name, sku, category, unit, buy, sell, stock, minimum, expiry):
        self.conn.execute("INSERT INTO products(name,sku,category,unit,buy_price,sell_price,stock,min_stock,expiry) VALUES(?,?,?,?,?,?,?,?,?)",
                          (name, sku, category, unit, buy, sell, stock, minimum, expiry))
        self.conn.commit()

    def add_contact(self, name, kind, phone):
        self.conn.execute("INSERT INTO contacts(name,kind,phone) VALUES(?,?,?)", (name, kind, phone))
        self.conn.commit()

    def add_expense(self, title, amount, category):
        self.conn.execute("INSERT INTO expenses(title,amount,category,created_at) VALUES(?,?,?,?)",
                          (title, amount, category, datetime.now().isoformat(timespec='seconds')))
        self.conn.commit()

    def create_invoice(self, kind, product_id, quantity, price, contact_id=None, paid=0):
        total = quantity * price
        number = f"{kind[:1].upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cur = self.conn.execute("INSERT INTO invoices(number,kind,contact_id,total,paid,created_at) VALUES(?,?,?,?,?,?)",
                                (number, kind, contact_id, total, paid, datetime.now().isoformat(timespec='seconds')))
        invoice_id = cur.lastrowid
        self.conn.execute("INSERT INTO invoice_items(invoice_id,product_id,quantity,price) VALUES(?,?,?,?)",
                          (invoice_id, product_id, quantity, price))
        delta = -quantity if kind == 'sale' else quantity
        self.conn.execute("UPDATE products SET stock=stock+? WHERE id=?", (delta, product_id))
        if contact_id:
            balance_delta = total - paid
            if kind == 'sale':
                self.conn.execute("UPDATE contacts SET balance=balance+? WHERE id=?", (balance_delta, contact_id))
            else:
                self.conn.execute("UPDATE contacts SET balance=balance-? WHERE id=?", (balance_delta, contact_id))
        self.conn.commit()
        return number


class RTLLabel(Label):
    def __init__(self, **kwargs):
        kwargs.setdefault('halign', 'right')
        kwargs.setdefault('text_size', (None, None))
        super().__init__(**kwargs)


class BaseScreen(Screen):
    title = StringProperty('')
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()

    def root_layout(self):
        box = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        header = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        back = Button(text='‹ القائمة', size_hint_x=None, width=dp(100), background_color=(0.05,0.32,0.45,1))
        back.bind(on_release=lambda *_: setattr(self.manager, 'current', 'dashboard'))
        header.add_widget(back)
        header.add_widget(Label(text=self.title, font_size='22sp', bold=True))
        box.add_widget(header)
        return box

    def input_row(self, parent, label, hint, key, numeric=False):
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        row.add_widget(RTLLabel(text=label, size_hint_x=.32))
        inp = TextInput(hint_text=hint, multiline=False, halign='right', input_filter='float' if numeric else None)
        row.add_widget(inp)
        parent.add_widget(row)
        setattr(self, key, inp)

    def toast(self, text):
        Popup(title='تم', content=Label(text=text), size_hint=(.8, .25)).open()


class DashboardScreen(BaseScreen):
    title = 'لوحة التحكم'
    def on_enter(self):
        self.clear_widgets()
        box = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
        box.add_widget(Label(text='نظام حساباتي', font_size='28sp', bold=True, color=(.05,.32,.45,1), size_hint_y=None, height=dp(65)))
        box.add_widget(RTLLabel(text='إدارة المبيعات والمشتريات والمخزون والحسابات من مكان واحد', size_hint_y=None, height=dp(42)))
        metrics = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(140))
        db = self.app.db
        cards = [('مبيعات اليوم', db.scalar("SELECT COALESCE(SUM(total),0) FROM invoices WHERE kind='sale' AND date(created_at)=date('now','localtime')")),
                 ('مشتريات اليوم', db.scalar("SELECT COALESCE(SUM(total),0) FROM invoices WHERE kind='purchase' AND date(created_at)=date('now','localtime')")),
                 ('عدد الأصناف', db.scalar('SELECT COUNT(*) FROM products')), ('تنبيه مخزون', db.scalar('SELECT COUNT(*) FROM products WHERE stock<=min_stock'))]
        for name, value in cards:
            metrics.add_widget(Label(text=f'{name}\n{float(value):,.2f}', font_size='18sp', color=(1,1,1,1), halign='center', valign='middle', text_size=(None,None), background_color=(.05,.32,.45,1)))
        box.add_widget(metrics)
        menu = GridLayout(cols=2, spacing=dp(10), padding=dp(2))
        items = [('فاتورة بيع', 'sale'), ('فاتورة شراء', 'purchase'), ('الأصناف والمخزون', 'products'), ('العملاء والموردون', 'contacts'), ('المصروفات', 'expenses'), ('التقارير', 'reports')]
        for text, screen in items:
            b = Button(text=text, font_size='18sp', background_color=(.12,.55,.52,1))
            b.bind(on_release=lambda btn, s=screen: setattr(self.manager, 'current', s))
            menu.add_widget(b)
        box.add_widget(menu)
        box.add_widget(Label(text='بياناتك محفوظة محلياً على الجهاز | النسخة الأولى', size_hint_y=None, height=dp(35), color=(.35,.35,.35,1)))
        self.add_widget(box)


class ProductsScreen(BaseScreen):
    title = 'الأصناف والمخزون'
    def on_enter(self):
        self.clear_widgets(); box = self.root_layout()
        form = GridLayout(cols=2, size_hint_y=None, height=dp(245), spacing=dp(5))
        for label, hint, key, numeric in [('اسم الصنف','مثال: قهوة عربية','pname',False),('الباركود','اختياري','psku',False),('التصنيف','غذائيات / دواء','pcat',False),('الوحدة','قطعة / كجم','punit',False),('سعر الشراء','0','pbuy',True),('سعر البيع','0','psell',True),('الكمية الحالية','0','pstock',True),('حد التنبيه','0','pmin',True),('تاريخ الانتهاء','YYYY-MM-DD','pexp',False),('','', 'dummy', False)]:
            if key == 'dummy': form.add_widget(Label()); form.add_widget(Label()); continue
            self.input_row(form, label, hint, key, numeric)
        add = Button(text='حفظ الصنف', size_hint_y=None, height=dp(48), background_color=(.05,.32,.45,1)); add.bind(on_release=self.save_product); box.add_widget(form); box.add_widget(add)
        scroll = ScrollView(); self.list_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None); self.list_box.bind(minimum_height=self.list_box.setter('height')); scroll.add_widget(self.list_box); box.add_widget(scroll); self.add_widget(box); self.refresh()
    def save_product(self, *_):
        if not self.pname.text.strip(): return self.toast('اكتب اسم الصنف أولاً')
        vals = [self.pname.text, self.psku.text, self.pcat.text, self.punit.text or 'قطعة']
        nums = [float(x.text or 0) for x in (self.pbuy,self.psell,self.pstock,self.pmin)]
        self.app.db.add_product(*vals, *nums, self.pexp.text); self.toast('تم حفظ الصنف'); self.on_enter()
    def refresh(self):
        for p in self.app.db.rows('SELECT * FROM products ORDER BY id DESC'):
            self.list_box.add_widget(RTLLabel(text=f"{p['name']}  |  مخزون: {p['stock']:g}  |  بيع: {p['sell_price']:,.2f}  |  {p['category']}", size_hint_y=None, height=dp(36)))


class InvoiceScreen(BaseScreen):
    kind = 'sale'
    title = 'فاتورة بيع'
    def on_enter(self):
        self.clear_widgets(); box=self.root_layout(); form=GridLayout(cols=2, size_hint_y=None, height=dp(245), spacing=dp(6))
        self.input_row(form,'رقم الصنف','ID الصنف','iid',True); self.input_row(form,'الكمية','1','qty',True); self.input_row(form,'السعر','اتركه فارغاً للسعر الافتراضي','price',True); self.input_row(form,'المدفوع','0','paid',True); self.input_row(form,'معرّف العميل/المورد','اختياري','cid',True)
        form.add_widget(Label()); form.add_widget(Label()); box.add_widget(form)
        hint='أدخل معرّف الصنف من قاعدة البيانات. راجع شاشة الأصناف.'; box.add_widget(RTLLabel(text=hint,size_hint_y=None,height=dp(35)))
        b=Button(text='حفظ الفاتورة وتحديث المخزون',size_hint_y=None,height=dp(52),background_color=(.12,.55,.52,1)); b.bind(on_release=self.save); box.add_widget(b); self.add_widget(box)
    def save(self,*_):
        try:
            product=self.app.db.rows('SELECT * FROM products WHERE id=?',(int(float(self.iid.text)),))[0]
            qty=float(self.qty.text or 1)
            default_price = product['sell_price'] if self.kind == 'sale' else product['buy_price']
            price=float(self.price.text) if self.price.text.strip() else float(default_price)
            paid=float(self.paid.text or 0)
            cid=int(float(self.cid.text)) if self.cid.text else None
            if self.kind=='sale' and product['stock']<qty: return self.toast('الكمية المطلوبة أكبر من المخزون')
            number=self.app.db.create_invoice(self.kind,product['id'],qty,price,cid,paid); self.toast(f'تم حفظ الفاتورة {number}')
        except (ValueError, IndexError): self.toast('تحقق من البيانات ومعرّف الصنف')


class ContactsScreen(BaseScreen):
    title='العملاء والموردون'
    def on_enter(self):
        self.clear_widgets(); box=self.root_layout(); form=GridLayout(cols=2,size_hint_y=None,height=dp(145),spacing=dp(6)); self.input_row(form,'الاسم','اسم العميل أو المورد','cname'); self.input_row(form,'النوع','عميل أو مورد','ckind'); self.input_row(form,'الهاتف','اختياري','cphone'); form.add_widget(Label()); box.add_widget(form); b=Button(text='حفظ جهة الاتصال',size_hint_y=None,height=dp(48)); b.bind(on_release=self.save); box.add_widget(b); sc=ScrollView(); self.lb=GridLayout(cols=1,size_hint_y=None); self.lb.bind(minimum_height=self.lb.setter('height')); sc.add_widget(self.lb); box.add_widget(sc); self.add_widget(box); self.refresh()
    def save(self,*_):
        if self.cname.text.strip(): self.app.db.add_contact(self.cname.text,self.ckind.text or 'عميل',self.cphone.text); self.on_enter()
    def refresh(self):
        for c in self.app.db.rows('SELECT * FROM contacts ORDER BY id DESC'): self.lb.add_widget(RTLLabel(text=f"#{c['id']}  {c['name']}  |  {c['kind']}  |  رصيد: {c['balance']:,.2f}",size_hint_y=None,height=dp(38)))


class ExpensesScreen(BaseScreen):
    title='المصروفات'
    def on_enter(self):
        self.clear_widgets(); box=self.root_layout(); form=GridLayout(cols=2,size_hint_y=None,height=dp(145),spacing=dp(6)); self.input_row(form,'البيان','إيجار / كهرباء / نقل','etitle'); self.input_row(form,'المبلغ','0','eamount',True); self.input_row(form,'التصنيف','تشغيلي','ecat'); form.add_widget(Label()); box.add_widget(form); b=Button(text='تسجيل المصروف',size_hint_y=None,height=dp(48)); b.bind(on_release=self.save); box.add_widget(b); self.add_widget(box)
    def save(self,*_):
        try: self.app.db.add_expense(self.etitle.text,float(self.eamount.text),self.ecat.text); self.toast('تم تسجيل المصروف')
        except ValueError: self.toast('أدخل مبلغاً صحيحاً')


class ReportsScreen(BaseScreen):
    title='التقارير'
    def on_enter(self):
        self.clear_widgets(); box=self.root_layout(); db=self.app.db; sales=db.scalar("SELECT COALESCE(SUM(total),0) FROM invoices WHERE kind='sale'"); purchases=db.scalar("SELECT COALESCE(SUM(total),0) FROM invoices WHERE kind='purchase'"); expenses=db.scalar('SELECT COALESCE(SUM(amount),0) FROM expenses'); stock=db.scalar('SELECT COALESCE(SUM(stock*buy_price),0) FROM products');
        report=f"إجمالي المبيعات: {sales:,.2f}\nإجمالي المشتريات: {purchases:,.2f}\nإجمالي المصروفات: {expenses:,.2f}\nالربح التقريبي: {sales-purchases-expenses:,.2f}\nقيمة المخزون بسعر التكلفة: {stock:,.2f}\n\nعدد الفواتير: {db.scalar('SELECT COUNT(*) FROM invoices')}\nالعملاء والموردون: {db.scalar('SELECT COUNT(*) FROM contacts')}"
        box.add_widget(RTLLabel(text=report,font_size='20sp',valign='top')); self.add_widget(box)


class AccountingApp(App):
    title='حساباتي - محاسبة'
    def build(self):
        os.makedirs(self.user_data_dir, exist_ok=True)
        db_path = Path(self.user_data_dir) / 'accounting.db'
        self.db = Database(db_path)
        sm=ScreenManager(); sm.add_widget(DashboardScreen(name='dashboard')); sm.add_widget(ProductsScreen(name='products')); sm.add_widget(ContactsScreen(name='contacts')); sm.add_widget(ExpensesScreen(name='expenses')); sm.add_widget(ReportsScreen(name='reports'))
        sale=InvoiceScreen(name='sale'); sale.kind='sale'; sale.title='فاتورة بيع'; sm.add_widget(sale); purchase=InvoiceScreen(name='purchase'); purchase.kind='purchase'; purchase.title='فاتورة شراء'; sm.add_widget(purchase)
        return sm


if __name__ == '__main__':
    AccountingApp().run()
