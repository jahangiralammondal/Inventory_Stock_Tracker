import unittest
from decimal import Decimal as D
from inventory import Warehouse, closing_quantity, status, bill, money


class StockRules(unittest.TestCase):
    def test_lookup_and_shared_bins(self):
        items = [dict(sku=s, aisle=3, bin_no=2) for s in ("SSD", "RAM")]
        stock = Warehouse(items)
        self.assertEqual(stock.aisles, [[], [], [[], items]])
        self.assertIs(stock.lookup(" ssd "), stock.aisles[2][1][0])
        self.assertIsNone(stock.lookup("missing"))

    def test_threshold_and_zero(self):
        self.assertEqual([status(n,5) for n in (6,5,4,0)],
                         ["In stock","Low stock","Low stock","Out of stock"])

    def test_movement_types(self):
        for kind, expected in [("Purchase",13),("Sale",7),("Customer return",13),
                               ("Supplier return",7),("Count",3)]:
            self.assertEqual(closing_quantity(10,kind,3),expected)
        self.assertEqual(closing_quantity(3,"Count",0),0)

    def test_invalid_units(self):
        for kind,n in [("Sale",4),("Sale",0),("Count",-1),("Purchase","1.5"),("foo",1)]:
            with self.assertRaises(ValueError):
                closing_quantity(3,kind,n)

    def test_money(self):
        for n in ["1.234","NaN","-1","Infinity","10000000"]:
            with self.assertRaises(ValueError):
                money(n)
        self.assertEqual(money("2.10"),D("2.10"))

    def test_discount_before_tax(self):
        self.assertEqual(bill(2,D("99.95"),D("10"),D("18")),
                         (D("199.90"),D("19.99"),D("32.38"),D("212.29")))
