import base64
import datetime
import json
import requests

class DPDCloudException(BaseException):
    pass

class ZipCodeRules(object):

    def __init__(self, data):
        self.no_pickup_days = [self._parse_date(x) for x in data["NoPickupDays"].split(",")]
        self.country = data["Country"]
        self.zip_code = data["ZipCode"]
        self.classic_cutoff = self._parse_time(data["ClassicCutOff"])
        self.express_cutoff = self._parse_time(data["ExpressCutOff"])

    def _parse_date(self, date_str):
        p = [int(x) for x in date_str.split(".")]
        return datetime.date(p[2], p[1], p[0])

    def _parse_time(self, time_str):
        p = [int(x) for x in time_str.split(":")]
        return datetime.time(*p)

    def next_pickup_date(self, after=None):
        current = after or datetime.date.today()
        while current.weekday() > 5 or current in self.no_pickup_days:
            current = datetime.timedelta(days=1)
        return current

class Address(object):

    def __init__(self, company=None, salutation=None, name=None, street=None, house_no=None, country=None, zip_code=None, city=None, state=None, phone=None, mail=None):
        self.company = company
        self.salutation = salutation
        self.name = name
        self.street = street
        self.house_no = house_no
        self.country = country
        self.zip_code = zip_code
        self.city = city
        self.state = state
        self.phone = phone
        self.mail = mail

    def to_dict(self):
        result = {
            "Street": self.street,
            "HouseNo": self.house_no or "",
            "Country": self.country,
            "ZipCode": self.zip_code,
            "City": self.city,
        }

        if self.company:
            result["Company"] = self.company
        if self.salutation:
            result["Salutation"] = self.salutation
        if self.name:
            result["Name"] = self.name

        if self.state:
            result["State"] = self.state
        if self.phone:
            result["phone"] = self.phone
        if self.mail:
            result["mail"] = self.mail

        return result

class Parcel(object):

    SERVICE_CLASSIC = "Classic"
    SERVICE_CLASSIC_PREDICT = "Classic_Predict"
    SERVICE_CLASSIC_COD = "Classic_COD"
    SERVICE_CLASSIC_COD_PREDICT = "Classic_COD_Predict"
    SERVICE_SHOP_DELIVERY = "Shop_Delivery"
    SERVICE_SHOP_RETURN = "Shop_Return"
    SERVICE_CLASSIC_RETURN = "Classic_Return"

    SERVICE_EXPRESS_830 = "Express_830"
    SERVICE_EXPRESS_830_COD = "Express_830_COD"
    SERVICE_EXPRESS_10 = "Express_10"
    SERVICE_EXPRESS_10_COD = "Express_10_COD"
    SERVICE_EXPRESS_12 = "Express_12"
    SERVICE_EXPRESS_12_COD = "Express_12_COD"
    SERVICE_EXPRESS_18 = "Express_18"
    SERVICE_EXPRESS_18_COD = "Express_18_COD"
    SERVICE_EXPRESS_12_SATURDAY = "Express_12_Saturday"
    SERVICE_EXPRESS_12_COD_SATURDAY = "Express_12_COD_Saturday"

    def __init__(self, address=None, service=SERVICE_CLASSIC, weight=None, content=None, internal_id=None, reference1=None, reference2=None):
        self.address = address
        self.service = service
        self.weight = weight
        self.content = content
        self.internal_id = internal_id
        self.reference1 = reference1
        self.reference2 = reference2
        self.label = None

    def to_dict(self):
        result = {
            "ShipAddress": self.address.to_dict(),
            "ParcelData": {
                "ShipService": self.service,
                "Weight": "%0.1f" % self.weight,
                "Content": self.content or "n/a",
                "YourInternalID": self.internal_id or "\u00A0",
                "Reference1": self.reference1 or "\u00A0",
                "Reference2": self.reference2 or "\u00A0"
            }
        }
        return result

class DPDCloud(object):

    API_VERSION = 100
    API_LANGUAGE = "de_DE"

    LABEL_SIZE_A4 = "PDF_A4"
    LABEL_SIZE_A6 = "PDF_A6"

    def __init__(self, api_endpoint, partner_name, partner_token, user_id, user_token):
        self._api_endpoint = api_endpoint
        self._partner_name = partner_name
        self._partner_token = partner_token
        self._user_id = user_id
        self._user_token = user_token

        self._session = requests.Session()

    def _request(self, url, data=None):
        headers = {
            "Version": str(self.API_VERSION),
            "Language": self.API_LANGUAGE,
            "PartnerCredentials-Name": self._partner_name,
            "PartnerCredentials-Token": self._partner_token,
            "UserCredentials-cloudUserID": self._user_id,
            "UserCredentials-Token": self._user_token
        }
        if data:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data)
            req = requests.Request("POST", self._api_endpoint + url, data=body, headers=headers)
        else:
            req = requests.Request("GET", self._api_endpoint + url, headers=headers)
        prepped = req.prepare()
        return self._session.send(prepped)

    def zipcode_rules(self):
        if not hasattr(self, "_zipcode_rules"):
            resp = self._request("ZipCodeRules")
            self._zipcode_rules = ZipCodeRules(resp.json()["ZipCodeRules"])
        return self._zipcode_rules

    def check_address(self, address):
        parcel = Parcel(address=address, service=Parcel.SERVICE_CLASSIC, weight=1)
        data = {
            "OrderAction": "checkOrderData",
            "OrderSettings": {
                "ShipDate": self.zipcode_rules().next_pickup_date().strftime("%Y-%m-%d"),
                "LabelSize": self.LABEL_SIZE_A6
            },
            "OrderDataList": [parcel.to_dict()]
        }
        resp = self._request("setOrder", data)
        return resp.json()["Ack"]

    def create_parcel(self, parcel, ship_date=None, label_size=LABEL_SIZE_A6, label_start_position="UpperLeft"):
        if not ship_date:
            ship_date = self.zipcode_rules().next_pickup_date()

        data = {
            "OrderAction": "startOrder",
            "OrderSettings": {
                "ShipDate": ship_date.strftime("%Y-%m-%d"),
                "LabelSize": label_size,
                "LabelStartPosition": label_start_position
            },
            "OrderDataList": [parcel.to_dict()]
        }
        resp = self._request("setOrder", data)
        data = resp.json()
        if not data["Ack"]:
            raise DPDCloudException(data["ErrorDataList"][0]["ErrorMsgLong"])
        parcel.parcel_no = data["LabelResponse"]["LabelDataList"][0]["ParcelNo"]
        parcel.label = base64.b64decode(data["LabelResponse"]["LabelPDF"].encode("ascii"))
