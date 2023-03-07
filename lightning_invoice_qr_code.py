import io
import pyzbar.pyzbar as pyzbar
import qrcode
import os
from PIL import Image
from pyln.client import LightningRpc
import hashlib
import requests


class InvalidFileError(Exception):
    pass


class RpcConnectionError(Exception):
    pass


def prompt_for_rpc_path():
    rpc_path = input("Enter path to your lightning-rpc: ")
    if not os.path.isfile(rpc_path):
        raise InvalidFileError("File path is not valid")

    try:
        rpc = LightningRpc(rpc_path)
    except:
        raise RpcConnectionError("Unable to connect to RPC server")

    return rpc


def generate_qr_code(invoice):
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(invoice)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_path = input("Enter file path to save QR code image: ")
    img.save(img_path)
    print("QR code image saved to:", img_path)


def decode_qr_code():
    img_path = input("Enter path to image file containing QR code: ")
    with open(img_path, 'rb') as image_file:
        image = Image.open(io.BytesIO(image_file.read()))
        image.load()

    codes = pyzbar.decode(image)
    invoice = codes[0].data.decode('utf-8')

    return invoice


def check_payment_details(invoice, rpc):
    payment_details = rpc.decodepay(invoice)

    amount = payment_details['msatoshi'] / 1000
    description = payment_details['description']
    payment_hash = payment_details['payment_hash']
    payee_node_id = payment_details['payee_node_id']

    if amount <= 0:
        return "Invalid payment amount"
    if "hack" in description.lower() or "malicious" in description.lower():
        return "Malicious invoice description"

    decoded = rpc.decodepay(invoice['bolt11'])
    if decoded['payment_hash'] != payment_hash:
        return "Invalid payment hash"

    with requests.Session() as session:
        r = session.get("https://1ml.com/node/" + payee_node_id)
        if r.status_code != 200:
            return "Invalid payee node ID"

    payment_status = rpc.listinvoices(payment_hash)['invoices'][0]['status']
    if payment_status != 'unpaid':
        return "Invoice has already been paid"

    expiry = decoded['expiry']
    if expiry <= 0:
        return "Invoice has expired"

    if not decoded['payment_preimage']:
        return "Invalid payment preimage"

    if decoded['description_hash'] is not None:
        return "Invoice covers another invoice"

    return "Invoice is valid"


def main():
    try:
        rpc = prompt_for_rpc_path()
    except InvalidFileError as e:
        print("Error: ", e)
        return
    except RpcConnectionError as e:
        print("Error: ", e)
        return

    invoice = input("Enter Lightning invoice: ")
    generate_qr_code(invoice)

    invoice = decode_qr_code()

    result = check_payment_details(invoice, rpc)
    print(result)


if __name__ == "__main__":
    main()
