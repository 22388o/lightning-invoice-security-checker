import io
import zbarlight
import qrcode
import os
from PIL import Image
from pyln.client import LightningRpc
import hashlib
import requests

# prompt user for RPC connection details
rpc_path = input("Enter path to your lightning-rpc: ")
if not os.path.isfile(rpc_path):
    print("Error: File path is not valid")
    exit()

try:
    rpc = LightningRpc(rpc_path)
except:
    print("Error: Unable to connect to RPC server")
    exit()


def check_invoice(invoice):
    # get payment details from the invoice
    amount = invoice['msatoshi'] / 1000
    description = invoice['description']
    payment_hash = invoice['payment_hash']
    payee_node_id = invoice['payee_node_id']

    # check that the payment amount and description are not malicious
    if amount <= 0:
        return "Invalid payment amount"
    if "hack" in description.lower() or "malicious" in description.lower():
        return "Malicious description"

    # check that the payment hash matches the invoice
    decoded = rpc.decodepay(invoice['bolt11'])
    if decoded['payment_hash'] != payment_hash:
        return "Invalid payment hash"

    # check that the payee's node ID is valid
    with requests.Session() as session:
        r = session.get("https://1ml.com/node/" + payee_node_id)
        if r.status_code != 200:
            return "Invalid payee node ID"

    # check that the invoice has not already been paid
    payment_status = rpc.listinvoices(payment_hash)['invoices'][0]['status']
    if payment_status != 'unpaid':
        return "Invoice has already been paid"

    # check that the invoice has not expired
    expiry = decoded['expiry']
    if expiry <= 0:
        return "Invoice has expired"

    # check that the payment preimage is valid
    payment_preimage = decoded['payment_preimage']
    if not payment_preimage:
        return "Invalid payment preimage"

    # check for any triggers after loading the invoice
    if decoded['description_hash'] is not None:
        # check if there is another invoice covered by this one
        covered_invoice_hash = hashlib.sha256(
            decoded['description_hash'].encode()).hexdigest()
        covered_invoice = rpc.listinvoices(covered_invoice_hash)
        if len(covered_invoice['invoices']) > 0:
            return "Invoice covers another invoice"

    # invoice is valid
    return "Invoice is valid"


# generate QR code for Lightning invoice
invoice = input("Enter Lightning invoice: ")
qr = qrcode.QRCode(
    version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
qr.add_data(invoice)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
img.show()

# decode QR code to get Lightning invoice
img_path = input("Enter path to image file containing QR code: ")
with open(img_path, 'rb') as image_file:
    image = Image.open(io.BytesIO(image_file.read()))
    image.load()

codes = zbarlight.scan_codes('qrcode', image)
invoice = codes[0].decode('utf-8')

# check validity of invoice
result = check_invoice(rpc.decodepay(invoice))
print(result)
