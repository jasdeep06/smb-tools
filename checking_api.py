from datetime import date, datetime
from typing import List, Optional, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    Date,
    DateTime,
    Integer,
    Numeric,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

# ---------------------------------------------------------------------
# DB SETUP
# ---------------------------------------------------------------------

# 👇 Replace with your Neon URL
DATABASE_URL = "postgresql://neondb_owner:npg_0DuGvNZOK2AL@ep-raspy-voice-adgxwy8e-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------
# ORM MODELS (match your smb_banking schema)
# ---------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text)
    phone = Column(Text)
    segment = Column(Text)


class Business(Base):
    __tablename__ = "businesses"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    customer_id = Column(Text, ForeignKey("customers.id"))
    legal_name = Column(Text, nullable=False)
    trade_name = Column(Text)
    entity_type = Column(Text, nullable=False)
    tax_id = Column(Text)
    registration_number = Column(Text)
    industry_code = Column(Text)
    country = Column(Text, nullable=False)
    state = Column(Text)
    city = Column(Text)
    address = Column(Text)
    years_in_business = Column(Integer)

    customer = relationship("Customer")
    checking_applications = relationship(
        "CheckingApplication", back_populates="business"
    )


class CheckingApplication(Base):
    __tablename__ = "checking_applications"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    reference = Column(Text, unique=True, nullable=False)
    business_id = Column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    customer_id = Column(Text, ForeignKey("customers.id"))
    product_id = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    status = Column(Text, nullable=False, default="RECEIVED")
    usage_profile = Column(JSONB)
    funding_preferences = Column(JSONB)

    business = relationship("Business", back_populates="checking_applications")
    customer = relationship("Customer")
    owners = relationship(
        "CheckingOwner", back_populates="application", cascade="all, delete-orphan"
    )
    documents = relationship(
        "CheckingDocument", back_populates="application", cascade="all, delete-orphan"
    )
    risk_scores = relationship(
        "CheckingRiskScore", back_populates="application", cascade="all, delete-orphan"
    )
    accounts = relationship(
        "CheckingAccount", back_populates="application", cascade="all, delete-orphan"
    )


class CheckingOwner(Base):
    __tablename__ = "checking_owners"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    checking_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("checking_applications.id"), nullable=False
    )
    full_name = Column(Text, nullable=False)
    dob = Column(Date)
    national_id = Column(Text)
    ownership_percentage = Column(Numeric)
    address = Column(Text)

    application = relationship("CheckingApplication", back_populates="owners")


class CheckingDocument(Base):
    __tablename__ = "checking_documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    checking_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("checking_applications.id"), nullable=False
    )
    doc_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False)  # UPLOADED, VALIDATED, REJECTED
    reason_codes = Column(ARRAY(Text), default=[])
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    application = relationship("CheckingApplication", back_populates="documents")


class CheckingRiskScore(Base):
    __tablename__ = "checking_risk_scores"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    checking_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("checking_applications.id"), nullable=False
    )
    risk_score = Column(Integer, nullable=False)
    risk_band = Column(Text, nullable=False)
    driver_codes = Column(ARRAY(Text), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    application = relationship("CheckingApplication", back_populates="risk_scores")


class CheckingAccount(Base):
    __tablename__ = "checking_accounts"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    checking_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("checking_applications.id"), nullable=False
    )
    account_number = Column(Text, nullable=False)
    routing_number = Column(Text)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    application = relationship("CheckingApplication", back_populates="accounts")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    context_type = Column(
        Text, nullable=False
    )  # CHECKING_APPLICATION, LENDING_APPLICATION, etc.
    context_id = Column(PGUUID(as_uuid=True), nullable=False)
    channel = Column(Text, nullable=False)  # EMAIL, SMS, APP
    decision = Column(Text, nullable=False)  # APPROVED, REJECTED
    reason_codes = Column(ARRAY(Text), nullable=False)
    delivery_status = Column(Text, nullable=False, default="SENT")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# NOTE: tables already exist from your SQL script, so no need to call create_all()


# ---------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------

DecisionLiteral = Literal["APPROVED", "REJECTED"]
ChannelLiteral = Literal["EMAIL", "SMS", "APP"]
RiskBandLiteral = Literal["LOW", "MEDIUM", "HIGH"]


class BusinessData(BaseModel):
    legal_name: str
    trade_name: Optional[str]
    entity_type: str
    tax_id: Optional[str]
    registration_number: Optional[str]
    industry_code: Optional[str]
    country: str
    state: Optional[str]
    city: Optional[str]
    address: Optional[str]
    years_in_business: Optional[int]


class OwnerData(BaseModel):
    owner_id: UUID
    full_name: str
    dob: Optional[date]
    national_id: Optional[str]
    ownership_percentage: Optional[float]
    address: Optional[str]


class UsageProfile(BaseModel):
    expected_monthly_credits: Optional[float] = None
    expected_monthly_debits: Optional[float] = None
    cash_deposit_volume_per_month: Optional[float] = None
    digital_payment_share: Optional[float] = None
    minimum_balance_comfort: Optional[float] = None


class FundingPreferences(BaseModel):
    method: Optional[str] = None
    amount: Optional[float] = None


class ApplicationData(BaseModel):
    application_id: UUID
    business_id: UUID
    customer_id: Optional[str]
    product_id: str
    submitted_at: datetime
    status: str
    business: BusinessData
    owners: List[OwnerData]
    usage_profile: Optional[UsageProfile]
    funding_preferences: Optional[FundingPreferences]


class GetCheckingApplicationByReferenceRequest(BaseModel):
    reference: str


class GetCheckingApplicationByReferenceResponse(BaseModel):
    application: ApplicationData


class EvaluateCompletenessRequest(BaseModel):
    application_id: UUID


class EvaluateCompletenessResponse(BaseModel):
    can_proceed: bool
    missing_field_codes: List[str]
    comments: Optional[str]


class EvaluateProductEligibilityRequest(BaseModel):
    application_id: UUID
    product_id: str


class EvaluateProductEligibilityResponse(BaseModel):
    eligible: bool
    reason_codes: List[str]


class BusinessVerificationRequest(BaseModel):
    application_id: UUID


class BusinessVerificationResponse(BaseModel):
    status: Literal["PASSED", "FAILED", "MANUAL_REVIEW"]
    reason_codes: List[str]
    matched_registry_name: Optional[str] = None
    matched_registration_number: Optional[str] = None


class OwnerVerificationRequest(BaseModel):
    application_id: UUID


class OwnerVerificationResult(BaseModel):
    owner_id: UUID
    status: Literal["PASSED", "FAILED", "MANUAL_REVIEW"]
    reason_codes: List[str]


class OwnerVerificationResponse(BaseModel):
    overall_status: Literal["PASSED", "FAILED", "MANUAL_REVIEW"]
    owners: List[OwnerVerificationResult]


class EvaluateDocumentsRequest(BaseModel):
    application_id: UUID


class EvaluateDocumentsResponse(BaseModel):
    docs_ok: bool
    missing_doc_types: List[str]
    invalid_doc_types: List[str]
    reason_codes: List[str]


class ScoreRiskRequest(BaseModel):
    application_id: UUID


class ScoreRiskResponse(BaseModel):
    risk_score: int
    risk_band: RiskBandLiteral
    driver_codes: List[str]


class OpenAccountRequest(BaseModel):
    application_id: UUID


class OpenAccountResponse(BaseModel):
    account_id: UUID
    account_number: str
    routing_number: Optional[str]
    status: str


class SendFinalDecisionNotificationRequest(BaseModel):
    application_id: UUID
    channel: ChannelLiteral
    decision: DecisionLiteral
    reason_codes: List[str] = []
    # we’re sending decision for the *application*, not account, so no account_id here


class SendFinalDecisionNotificationResponse(BaseModel):
    notification_id: UUID
    delivery_status: str


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def require_checking_application(
    db: Session, application_id: UUID
) -> CheckingApplication:
    app_obj = (
        db.query(CheckingApplication)
        .filter(CheckingApplication.id == application_id)
        .first()
    )
    if not app_obj:
        raise HTTPException(status_code=404, detail="Checking application not found")
    return app_obj


def build_application_data(app_obj: CheckingApplication) -> ApplicationData:
    b = app_obj.business
    up = app_obj.usage_profile or {}
    fp = app_obj.funding_preferences or {}

    return ApplicationData(
        application_id=app_obj.id,
        business_id=app_obj.business_id,
        customer_id=app_obj.customer_id,
        product_id=app_obj.product_id,
        submitted_at=app_obj.submitted_at,
        status=app_obj.status,
        business=BusinessData(
            legal_name=b.legal_name,
            trade_name=b.trade_name,
            entity_type=b.entity_type,
            tax_id=b.tax_id,
            registration_number=b.registration_number,
            industry_code=b.industry_code,
            country=b.country,
            state=b.state,
            city=b.city,
            address=b.address,
            years_in_business=b.years_in_business,
        ),
        owners=[
            OwnerData(
                owner_id=o.id,
                full_name=o.full_name,
                dob=o.dob,
                national_id=o.national_id,
                ownership_percentage=float(o.ownership_percentage)
                if o.ownership_percentage is not None
                else None,
                address=o.address,
            )
            for o in app_obj.owners
        ],
        usage_profile=UsageProfile(**up) if up else None,
        funding_preferences=FundingPreferences(**fp) if fp else None,
    )


# ---------------------------------------------------------------------
# FastAPI app + endpoints
# ---------------------------------------------------------------------

app = FastAPI(title="Checking Onboarding API")


@app.post(
    "/checking/applications/get_by_reference",
    response_model=GetCheckingApplicationByReferenceResponse,
)
def get_application_by_reference(
    payload: GetCheckingApplicationByReferenceRequest,
    db: Session = Depends(get_db),
):
    app_obj = (
        db.query(CheckingApplication)
        .filter(CheckingApplication.reference == payload.reference)
        .first()
    )
    if not app_obj:
        raise HTTPException(
            status_code=404, detail="Application with given reference not found"
        )
    return GetCheckingApplicationByReferenceResponse(
        application=build_application_data(app_obj)
    )


@app.post(
    "/checking/applications/evaluate_completeness",
    response_model=EvaluateCompletenessResponse,
)
def evaluate_application_completeness(
    payload: EvaluateCompletenessRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)
    b = app_obj.business
    missing: List[str] = []

    if not b.tax_id:
        missing.append("BUSINESS_TAX_ID")
    if not b.address:
        missing.append("BUSINESS_ADDRESS")

    if not app_obj.owners:
        missing.append("OWNERS_MISSING")
    else:
        for o in app_obj.owners:
            if not o.dob:
                missing.append("OWNER_DOB")
            if not o.national_id:
                missing.append("OWNER_ID_NUMBER")
            if o.ownership_percentage is None:
                missing.append("OWNERSHIP_PERCENTAGE")

    if not app_obj.usage_profile:
        missing.append("USAGE_PROFILE_MISSING")

    missing = sorted(set(missing))
    can_proceed = len(missing) == 0
    comments = (
        None
        if can_proceed
        else "Mandatory fields missing; cannot proceed without user interaction."
    )

    return EvaluateCompletenessResponse(
        can_proceed=can_proceed,
        missing_field_codes=missing,
        comments=comments,
    )


@app.post(
    "/checking/applications/evaluate_product_eligibility",
    response_model=EvaluateProductEligibilityResponse,
)
def evaluate_product_eligibility(
    payload: EvaluateProductEligibilityRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)
    b = app_obj.business

    eligible = True
    reason_codes: List[str] = []

    # toy rules:
    # 1) block some "restricted" industry codes
    if b.industry_code in {"7995", "9999"}:
        eligible = False
        reason_codes.append("INDUSTRY_NOT_ALLOWED")

    # 2) very new business can't get "premium" products
    if (
        b.years_in_business is not None
        and b.years_in_business < 1
        and "PREMIUM" in payload.product_id.upper()
    ):
        eligible = False
        reason_codes.append("MIN_AGE_OF_BUSINESS_NOT_MET")

    return EvaluateProductEligibilityResponse(
        eligible=eligible, reason_codes=reason_codes
    )


@app.post(
    "/checking/applications/run_business_verification",
    response_model=BusinessVerificationResponse,
)
def run_business_verification(
    payload: BusinessVerificationRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)
    b = app_obj.business

    if not b.registration_number:
        return BusinessVerificationResponse(
            status="FAILED",
            reason_codes=["REGISTRATION_NOT_FOUND"],
            matched_registry_name=None,
            matched_registration_number=None,
        )

    # pretend registry lookup succeeded
    return BusinessVerificationResponse(
        status="PASSED",
        reason_codes=[],
        matched_registry_name=b.legal_name,
        matched_registration_number=b.registration_number,
    )


@app.post(
    "/checking/applications/run_owner_verification",
    response_model=OwnerVerificationResponse,
)
def run_owner_verification(
    payload: OwnerVerificationRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)
    if not app_obj.owners:
        return OwnerVerificationResponse(overall_status="FAILED", owners=[])

    overall_status: Literal["PASSED", "FAILED", "MANUAL_REVIEW"] = "PASSED"
    results: List[OwnerVerificationResult] = []

    for o in app_obj.owners:
        rc: List[str] = []
        status: Literal["PASSED", "FAILED", "MANUAL_REVIEW"] = "PASSED"

        if not o.national_id:
            rc.append("MISSING_NATIONAL_ID")
            status = "FAILED"
        if not o.dob:
            rc.append("MISSING_DOB")
            status = "FAILED"

        if status != "PASSED":
            overall_status = "FAILED"

        results.append(
            OwnerVerificationResult(
                owner_id=o.id,
                status=status,
                reason_codes=rc,
            )
        )

    return OwnerVerificationResponse(
        overall_status=overall_status,
        owners=results,
    )


@app.post(
    "/checking/applications/evaluate_documents",
    response_model=EvaluateDocumentsResponse,
)
def evaluate_document_set_for_application(
    payload: EvaluateDocumentsRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)

    required = {"BUSINESS_REG_CERT", "TAX_ID_PROOF", "OWNER_ID_PROOF"}
    docs_by_type = {d.doc_type: d for d in app_obj.documents}

    missing = [d for d in required if d not in docs_by_type]
    invalid_doc_types: List[str] = []
    reason_codes: List[str] = []

    for dt, doc in docs_by_type.items():
        if doc.status == "REJECTED":
            invalid_doc_types.append(dt)
            if doc.reason_codes:
                reason_codes.extend(doc.reason_codes)

    docs_ok = len(missing) == 0 and len(invalid_doc_types) == 0

    return EvaluateDocumentsResponse(
        docs_ok=docs_ok,
        missing_doc_types=missing,
        invalid_doc_types=invalid_doc_types,
        reason_codes=sorted(set(reason_codes)),
    )


@app.post("/checking/applications/score_risk", response_model=ScoreRiskResponse)
def score_application_risk(
    payload: ScoreRiskRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)
    b = app_obj.business
    up = app_obj.usage_profile or {}

    risk_score = 20
    drivers: List[str] = []

    # toy rules
    if b.years_in_business is not None and b.years_in_business < 1:
        risk_score += 30
        drivers.append("NEW_BUSINESS")

    cash_vol = float(up.get("cash_deposit_volume_per_month") or 0)
    if cash_vol > 100000:
        risk_score += 30
        drivers.append("HIGH_CASH_VOLUME")

    if b.industry_code in {"7995", "9999"}:
        risk_score += 20
        drivers.append("HIGH_RISK_INDUSTRY")

    if risk_score < 30:
        band: RiskBandLiteral = "LOW"
    elif risk_score < 70:
        band = "MEDIUM"
    else:
        band = "HIGH"

    if not drivers:
        drivers = ["BASELINE"]

    entry = CheckingRiskScore(
        checking_application_id=app_obj.id,
        risk_score=risk_score,
        risk_band=band,
        driver_codes=drivers,
    )
    db.add(entry)
    db.commit()

    return ScoreRiskResponse(
        risk_score=risk_score,
        risk_band=band,
        driver_codes=drivers,
    )


@app.post("/checking/applications/open_account", response_model=OpenAccountResponse)
def open_account_from_application(
    payload: OpenAccountRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)

    # if account already exists, just return it
    existing = app_obj.accounts[0] if app_obj.accounts else None
    if existing:
        return OpenAccountResponse(
            account_id=existing.id,
            account_number=existing.account_number,
            routing_number=existing.routing_number,
            status=existing.status,
        )

    # generate a toy account number
    account_number = "10" + str(app_obj.id).replace("-", "")[:10]
    routing_number = "011000015"

    acc = CheckingAccount(
        checking_application_id=app_obj.id,
        account_number=account_number,
        routing_number=routing_number,
        status="ACTIVE",
    )
    app_obj.status = "DECIDED"
    db.add(acc)
    db.commit()
    db.refresh(acc)

    return OpenAccountResponse(
        account_id=acc.id,
        account_number=acc.account_number,
        routing_number=acc.routing_number,
        status=acc.status,
    )


@app.post(
    "/checking/applications/send_final_decision_notification",
    response_model=SendFinalDecisionNotificationResponse,
)
def send_final_decision_notification(
    payload: SendFinalDecisionNotificationRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_checking_application(db, payload.application_id)

    notif = Notification(
        context_type="CHECKING_APPLICATION",
        context_id=app_obj.id,
        channel=payload.channel,
        decision=payload.decision,
        reason_codes=payload.reason_codes or [],
        delivery_status="SENT",
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    return SendFinalDecisionNotificationResponse(
        notification_id=notif.id,
        delivery_status=notif.delivery_status,
    )
