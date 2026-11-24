"""Warehouse model. Aisles and bins are numbered from 1 in the shop."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class Warehouse:
    def __init__(self, products):
        self.by_code = {}
        self.aisles = []
        for product in products:
            aisle, bin_no = product["aisle"], product["bin_no"]
            while len(self.aisles) < aisle:
                self.aisles.append([])
            bins = self.aisles[aisle - 1]
            while len(bins) < bin_no:
                bins.append([])
            bins[bin_no - 1].append(product)
            self.by_code[product["sku"]] = product

    def lookup(self, code):
        return self.by_code.get(code.strip().upper())


def status(quantity, minimum):
    if quantity == 0:
        return "Out of stock"
    return "Low stock" if quantity <= minimum else "In stock"


def integer(value, label, minimum=0, maximum=1000000):
    try:
        number = int(str(value))
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a whole number.") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return number


def money(value, maximum=Decimal("9999999.99")):
    try:
        amount = Decimal(str(value))
        if amount.is_finite() and 0 <= amount <= maximum and amount == amount.quantize(Decimal(".01")):
            return amount.quantize(Decimal(".01"))
    except (ValueError, InvalidOperation):
        pass
    raise ValueError(f"Enter an amount from 0 to {maximum} with up to two decimal places.")


def closing_quantity(current, kind, units):
    if kind == "Count":
        return integer(units, "Count")
    units = integer(units, "Units", 1)
    if kind in ("Purchase", "Customer return"):
        return integer(current + units, "Closing stock")
    if kind not in ("Sale", "Supplier return"):
        raise ValueError("Unknown movement type.")
    if units > current:
        raise ValueError(f"Only {current} units available.")
    return current - units


def bill(units, price, discount, tax):
    cent = Decimal(".01")
    subtotal = units * price
    reduction = (subtotal * discount / 100).quantize(cent, ROUND_HALF_UP)
    taxable = subtotal - reduction
    tax_amount = (taxable * tax / 100).quantize(cent, ROUND_HALF_UP)
    return subtotal, reduction, tax_amount, taxable + tax_amount
