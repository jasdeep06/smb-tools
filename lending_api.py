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
    Boolean,
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
# ORM MODELS
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


class CheckingAccount(Base):
    __tablename__ = "checking_accounts"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    checking_application_id = Column(PGUUID(as_uuid=True), nullable=False)
    account_number = Column(Text, nullable=False)
    routing_number = Column(Text)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class LendingApplication(Base):
    __tablename__ = "lending_applications"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    reference = Column(Text, unique=True, nullable=False)
    customer_id = Column(Text, ForeignKey("customers.id"))
    business_id = Column(PGUUID(as_uuid=True), ForeignKey("businesses.id"))
    checking_account_id = Column(
        PGUUID(as_uuid=True), ForeignKey("checking_accounts.id")
    )
    product_type = Column(Text, nullable=False)  # CREDIT_CARD, REVOLVING_LOC, TERM_LOAN
    requested_amount = Column(Numeric)
    status = Column(Text, nullable=False, default="RECEIVED")
    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    customer = relationship("Customer")
    business = relationship("Business")
    checking_account = relationship("CheckingAccount")
    transaction_summaries = relationship(
        "LendingTransactionSummary",
        back_populates="lending_application",
        cascade="all, delete-orphan",
    )
    credit_reports = relationship(
        "BusinessCreditReport",
        back_populates="lending_application",
        cascade="all, delete-orphan",
    )
    underwriting_results = relationship(
        "LendingUnderwriting",
        back_populates="lending_application",
        cascade="all, delete-orphan",
    )
    offers = relationship(
        "LendingOffer",
        back_populates="lending_application",
        cascade="all, delete-orphan",
    )
    facilities = relationship(
        "CreditFacility",
        back_populates="lending_application",
        cascade="all, delete-orphan",
    )


class LendingTransactionSummary(Base):
    __tablename__ = "lending_transaction_summaries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    lending_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("lending_applications.id"), nullable=False
    )
    checking_account_id = Column(
        PGUUID(as_uuid=True), ForeignKey("checking_accounts.id"), nullable=False
    )
    lookback_months = Column(Integer, nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    total_credits = Column(Numeric)
    total_debits = Column(Numeric)
    avg_monthly_revenue = Column(Numeric)
    revenue_volatility = Column(Numeric)
    max_single_month_revenue = Column(Numeric)
    months_with_negative_end_balance = Column(Integer)
    avg_end_of_month_balance = Column(Numeric)
    overdraft_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    lending_application = relationship(
        "LendingApplication", back_populates="transaction_summaries"
    )
    checking_account = relationship("CheckingAccount")


class BusinessCreditReport(Base):
    __tablename__ = "business_credit_reports"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    lending_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("lending_applications.id"), nullable=False
    )
    bureau = Column(Text, nullable=False)
    score = Column(Integer)
    score_band = Column(Text)
    delinquencies_count = Column(Integer)
    delinquencies_last_24m = Column(Integer)
    bankruptcies_count = Column(Integer)
    public_records_count = Column(Integer)
    utilization_ratio = Column(Numeric)
    last_updated_at = Column(DateTime(timezone=True))

    lending_application = relationship(
        "LendingApplication", back_populates="credit_reports"
    )


class LendingUnderwriting(Base):
    __tablename__ = "lending_underwriting"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    lending_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("lending_applications.id"), nullable=False
    )
    risk_grade = Column(Text)
    pd_estimate = Column(Numeric)
    lgd_estimate = Column(Numeric)
    recommended_max_exposure = Column(Numeric)
    affordability_band = Column(Text)
    key_risk_drivers = Column(ARRAY(Text))
    dscr = Column(Numeric)
    debt_to_revenue_ratio = Column(Numeric)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    lending_application = relationship(
        "LendingApplication", back_populates="underwriting_results"
    )


class LendingOffer(Base):
    __tablename__ = "lending_offers"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    lending_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("lending_applications.id"), nullable=False
    )
    offer_code = Column(Text, unique=True, nullable=False)
    product_type = Column(Text, nullable=False)
    credit_limit = Column(Numeric, nullable=False)
    min_credit_limit = Column(Numeric)
    max_credit_limit = Column(Numeric)
    apr = Column(Numeric)
    annual_fee = Column(Numeric)
    origination_fee = Column(Numeric)
    tenor_months = Column(Integer)
    repayment_terms = Column(Text)
    collateral_required = Column(
        Boolean, nullable=False, default=False
    )  # 👈 change this
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    lending_application = relationship("LendingApplication", back_populates="offers")


class CreditFacility(Base):
    __tablename__ = "credit_facilities"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    lending_application_id = Column(
        PGUUID(as_uuid=True), ForeignKey("lending_applications.id"), nullable=False
    )
    customer_id = Column(Text, ForeignKey("customers.id"))
    business_id = Column(PGUUID(as_uuid=True), ForeignKey("businesses.id"))
    facility_type = Column(Text, nullable=False)
    account_number = Column(Text, nullable=False)
    credit_limit = Column(Numeric, nullable=False)
    apr = Column(Numeric)
    status = Column(Text, nullable=False)
    billing_cycle_day = Column(Integer)
    drawdown_terms = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    lending_application = relationship(
        "LendingApplication", back_populates="facilities"
    )
    customer = relationship("Customer")
    business = relationship("Business")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    context_type = Column(Text, nullable=False)
    context_id = Column(PGUUID(as_uuid=True), nullable=False)
    channel = Column(Text, nullable=False)
    decision = Column(Text, nullable=False)
    reason_codes = Column(ARRAY(Text), nullable=False)
    delivery_status = Column(Text, nullable=False, default="SENT")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------

DecisionLiteral = Literal["APPROVED", "REJECTED"]
ChannelLiteral = Literal["EMAIL", "SMS", "APP"]


class CustomerSnapshot(BaseModel):
    customer_id: str
    segment: Optional[str]
    is_existing_borrower: Optional[bool] = None
    has_prior_defaults: Optional[bool] = None
    total_existing_exposure: Optional[float] = None


class BusinessSnapshot(BaseModel):
    business_id: UUID
    legal_name: str
    trade_name: Optional[str]
    industry_code: Optional[str]
    entity_type: str
    years_in_business: Optional[int]
    country: str
    state: Optional[str]
    city: Optional[str]


class CheckingSnapshot(BaseModel):
    checking_account_id: UUID
    tenure_months: Optional[int] = None
    avg_balance_last_6m: Optional[float] = None
    overdrafts_last_12m: Optional[int] = None
    is_primary_operating_account: Optional[bool] = True


class LendingProductSnapshot(BaseModel):
    product_type: str
    requested_amount: Optional[float]


class LendingApplicationFull(BaseModel):
    lending_application_id: UUID
    reference: str
    status: str
    submitted_at: datetime
    customer: CustomerSnapshot
    business: BusinessSnapshot
    checking_account: CheckingSnapshot
    lending_product: LendingProductSnapshot


class GetLendingApplicationByReferenceRequest(BaseModel):
    lending_application_reference: str


class GetLendingApplicationByReferenceResponse(BaseModel):
    application: LendingApplicationFull


class CheckingTransactionSummaryResponse(BaseModel):
    checking_account_id: UUID
    period_start: Optional[date]
    period_end: Optional[date]
    total_credits: Optional[float]
    total_debits: Optional[float]
    avg_monthly_revenue: Optional[float]
    revenue_volatility: Optional[float]
    max_single_month_revenue: Optional[float]
    months_with_negative_end_balance: Optional[int]
    avg_end_of_month_balance: Optional[float]
    overdraft_count: Optional[int]


class GetCheckingTransactionSummaryRequest(BaseModel):
    lending_application_id: UUID
    lookback_months: Optional[int] = 12


class PullBusinessCreditReportRequest(BaseModel):
    lending_application_id: UUID
    bureau: str


class BusinessCreditReportResponse(BaseModel):
    report_id: UUID
    bureau: str
    score: Optional[int]
    score_band: Optional[str]
    delinquencies_count: Optional[int]
    delinquencies_last_24m: Optional[int]
    bankruptcies_count: Optional[int]
    public_records_count: Optional[int]
    utilization_ratio: Optional[float]
    last_updated_at: Optional[datetime]


class GetLatestBusinessCreditReportRequest(BaseModel):
    lending_application_id: UUID


class EvaluateLendingPolicyEligibilityRequest(BaseModel):
    lending_application_id: UUID


class EvaluateLendingPolicyEligibilityResponse(BaseModel):
    eligible: bool
    reason_codes: List[str]


class RunLendingUnderwritingRequest(BaseModel):
    lending_application_id: UUID


class RunLendingUnderwritingResponse(BaseModel):
    underwriting_id: UUID
    risk_grade: str
    pd_estimate: float
    lgd_estimate: float
    recommended_max_exposure: float
    affordability_band: str
    key_risk_drivers: List[str]
    supporting_metrics: dict


class GenerateCreditLineOffersRequest(BaseModel):
    lending_application_id: UUID
    underwriting_id: Optional[UUID] = None


class Offer(BaseModel):
    offer_id: UUID
    product_type: str
    credit_limit: float
    min_credit_limit: Optional[float]
    max_credit_limit: Optional[float]
    apr: Optional[float]
    annual_fee: Optional[float]
    origination_fee: Optional[float]
    tenor_months: Optional[int]
    repayment_terms: Optional[str]
    collateral_required: bool
    notes: Optional[str]


class GenerateCreditLineOffersResponse(BaseModel):
    offers: List[Offer]


class SelectCreditOfferRequest(BaseModel):
    lending_application_id: UUID
    offer_id: UUID


class SelectCreditOfferResponse(BaseModel):
    status: str
    selected_offer_snapshot: Offer


class OpenCreditFacilityRequest(BaseModel):
    lending_application_id: UUID


class OpenCreditFacilityResponse(BaseModel):
    facility_id: UUID
    facility_type: str
    customer_id: str
    business_id: UUID
    account_number: str
    credit_limit: float
    apr: Optional[float]
    status: str
    billing_cycle_day: Optional[int]
    drawdown_terms: Optional[str]


class SendLendingDecisionNotificationRequest(BaseModel):
    lending_application_id: UUID
    channel: ChannelLiteral
    decision: DecisionLiteral
    reason_codes: List[str] = []


class SendLendingDecisionNotificationResponse(BaseModel):
    notification_id: UUID
    delivery_status: str


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def require_lending_application(db: Session, app_id: UUID) -> LendingApplication:
    app_obj = (
        db.query(LendingApplication).filter(LendingApplication.id == app_id).first()
    )
    if not app_obj:
        raise HTTPException(status_code=404, detail="Lending application not found")
    return app_obj


def build_lending_application_full(
    app_obj: LendingApplication,
) -> LendingApplicationFull:
    c = app_obj.customer
    b = app_obj.business
    ca = app_obj.checking_account

    # You don't currently store tenure/avg balance in DB, so these are left None / toy values.
    return LendingApplicationFull(
        lending_application_id=app_obj.id,
        reference=app_obj.reference,
        status=app_obj.status,
        submitted_at=app_obj.submitted_at,
        customer=CustomerSnapshot(
            customer_id=c.id,
            segment=c.segment,
            # toy values; normally computed from other tables
            is_existing_borrower=False,
            has_prior_defaults=False,
            total_existing_exposure=None,
        ),
        business=BusinessSnapshot(
            business_id=b.id,
            legal_name=b.legal_name,
            trade_name=b.trade_name,
            industry_code=b.industry_code,
            entity_type=b.entity_type,
            years_in_business=b.years_in_business,
            country=b.country,
            state=b.state,
            city=b.city,
        ),
        checking_account=CheckingSnapshot(
            checking_account_id=ca.id,
            tenure_months=None,
            avg_balance_last_6m=None,
            overdrafts_last_12m=None,
            is_primary_operating_account=True,
        ),
        lending_product=LendingProductSnapshot(
            product_type=app_obj.product_type,
            requested_amount=float(app_obj.requested_amount)
            if app_obj.requested_amount is not None
            else None,
        ),
    )


# ---------------------------------------------------------------------
# FastAPI app + endpoints
# ---------------------------------------------------------------------

app = FastAPI(title="Lending / Credit-Line API")


@app.post(
    "/lending/applications/get_by_reference",
    response_model=GetLendingApplicationByReferenceResponse,
)
def get_lending_application_by_reference(
    payload: GetLendingApplicationByReferenceRequest,
    db: Session = Depends(get_db),
):
    app_obj = (
        db.query(LendingApplication)
        .filter(LendingApplication.reference == payload.lending_application_reference)
        .first()
    )
    if not app_obj:
        raise HTTPException(
            status_code=404, detail="Lending application with given reference not found"
        )
    return GetLendingApplicationByReferenceResponse(
        application=build_lending_application_full(app_obj)
    )


@app.post(
    "/lending/checking_transaction_summary",
    response_model=CheckingTransactionSummaryResponse,
)
def get_checking_transaction_summary_for_lending(
    payload: GetCheckingTransactionSummaryRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)

    # For now, just return the latest summary if present, ignoring lookback_months
    summary = (
        db.query(LendingTransactionSummary)
        .filter(LendingTransactionSummary.lending_application_id == app_obj.id)
        .order_by(LendingTransactionSummary.created_at.desc())
        .first()
    )
    if not summary:
        # empty summary if none exists
        return CheckingTransactionSummaryResponse(
            checking_account_id=app_obj.checking_account_id,
            period_start=None,
            period_end=None,
            total_credits=None,
            total_debits=None,
            avg_monthly_revenue=None,
            revenue_volatility=None,
            max_single_month_revenue=None,
            months_with_negative_end_balance=None,
            avg_end_of_month_balance=None,
            overdraft_count=None,
        )

    return CheckingTransactionSummaryResponse(
        checking_account_id=summary.checking_account_id,
        period_start=summary.period_start,
        period_end=summary.period_end,
        total_credits=float(summary.total_credits)
        if summary.total_credits is not None
        else None,
        total_debits=float(summary.total_debits)
        if summary.total_debits is not None
        else None,
        avg_monthly_revenue=float(summary.avg_monthly_revenue)
        if summary.avg_monthly_revenue is not None
        else None,
        revenue_volatility=float(summary.revenue_volatility)
        if summary.revenue_volatility is not None
        else None,
        max_single_month_revenue=float(summary.max_single_month_revenue)
        if summary.max_single_month_revenue is not None
        else None,
        months_with_negative_end_balance=summary.months_with_negative_end_balance,
        avg_end_of_month_balance=float(summary.avg_end_of_month_balance)
        if summary.avg_end_of_month_balance is not None
        else None,
        overdraft_count=summary.overdraft_count,
    )


@app.post(
    "/lending/credit_report/pull",
    response_model=BusinessCreditReportResponse,
)
def pull_business_credit_report(
    payload: PullBusinessCreditReportRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)

    # In reality you'd call Experian/etc. Here we just reuse existing or create a toy one.
    existing = (
        db.query(BusinessCreditReport)
        .filter(
            BusinessCreditReport.lending_application_id == app_obj.id,
            BusinessCreditReport.bureau == payload.bureau,
        )
        .order_by(BusinessCreditReport.last_updated_at.desc())
        .first()
    )
    if existing:
        return BusinessCreditReportResponse(
            report_id=existing.id,
            bureau=existing.bureau,
            score=existing.score,
            score_band=existing.score_band,
            delinquencies_count=existing.delinquencies_count,
            delinquencies_last_24m=existing.delinquencies_last_24m,
            bankruptcies_count=existing.bankruptcies_count,
            public_records_count=existing.public_records_count,
            utilization_ratio=float(existing.utilization_ratio)
            if existing.utilization_ratio is not None
            else None,
            last_updated_at=existing.last_updated_at,
        )

    # toy fallback
    report = BusinessCreditReport(
        lending_application_id=app_obj.id,
        bureau=payload.bureau,
        score=80,
        score_band="GOOD",
        delinquencies_count=0,
        delinquencies_last_24m=0,
        bankruptcies_count=0,
        public_records_count=0,
        utilization_ratio=0.3,
        last_updated_at=datetime.utcnow(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return BusinessCreditReportResponse(
        report_id=report.id,
        bureau=report.bureau,
        score=report.score,
        score_band=report.score_band,
        delinquencies_count=report.delinquencies_count,
        delinquencies_last_24m=report.delinquencies_last_24m,
        bankruptcies_count=report.bankruptcies_count,
        public_records_count=report.public_records_count,
        utilization_ratio=float(report.utilization_ratio)
        if report.utilization_ratio is not None
        else None,
        last_updated_at=report.last_updated_at,
    )


@app.post(
    "/lending/credit_report/latest",
    response_model=Optional[BusinessCreditReportResponse],
)
def get_latest_business_credit_report(
    payload: GetLatestBusinessCreditReportRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)
    report = (
        db.query(BusinessCreditReport)
        .filter(BusinessCreditReport.lending_application_id == app_obj.id)
        .order_by(BusinessCreditReport.last_updated_at.desc())
        .first()
    )
    if not report:
        return None

    return BusinessCreditReportResponse(
        report_id=report.id,
        bureau=report.bureau,
        score=report.score,
        score_band=report.score_band,
        delinquencies_count=report.delinquencies_count,
        delinquencies_last_24m=report.delinquencies_last_24m,
        bankruptcies_count=report.bankruptcies_count,
        public_records_count=report.public_records_count,
        utilization_ratio=float(report.utilization_ratio)
        if report.utilization_ratio is not None
        else None,
        last_updated_at=report.last_updated_at,
    )


@app.post(
    "/lending/policy/evaluate",
    response_model=EvaluateLendingPolicyEligibilityResponse,
)
def evaluate_lending_policy_eligibility(
    payload: EvaluateLendingPolicyEligibilityRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)
    reason_codes: List[str] = []
    eligible = True

    # toy rules:
    # 1) reject if requested_amount is very high and years_in_business < 1
    b = app_obj.business
    requested = (
        float(app_obj.requested_amount) if app_obj.requested_amount is not None else 0.0
    )
    if (
        b.years_in_business is not None
        and b.years_in_business < 1
        and requested > 50000
    ):
        eligible = False
        reason_codes.append("INSUFFICIENT_TENURE_FOR_REQUESTED_AMOUNT")

    # 2) if there's a bureau report with low score, reject
    report = (
        db.query(BusinessCreditReport)
        .filter(BusinessCreditReport.lending_application_id == app_obj.id)
        .order_by(BusinessCreditReport.last_updated_at.desc())
        .first()
    )
    if report and report.score is not None and report.score < 50:
        eligible = False
        reason_codes.append("LOW_BUREAU_SCORE")

    return EvaluateLendingPolicyEligibilityResponse(
        eligible=eligible, reason_codes=reason_codes
    )


@app.post(
    "/lending/underwriting/run",
    response_model=RunLendingUnderwritingResponse,
)
def run_lending_underwriting(
    payload: RunLendingUnderwritingRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)
    b = app_obj.business

    summary = (
        db.query(LendingTransactionSummary)
        .filter(LendingTransactionSummary.lending_application_id == app_obj.id)
        .order_by(LendingTransactionSummary.created_at.desc())
        .first()
    )
    report = (
        db.query(BusinessCreditReport)
        .filter(BusinessCreditReport.lending_application_id == app_obj.id)
        .order_by(BusinessCreditReport.last_updated_at.desc())
        .first()
    )

    avg_rev = (
        float(summary.avg_monthly_revenue)
        if summary and summary.avg_monthly_revenue is not None
        else 0.0
    )
    score = report.score if report and report.score is not None else 75

    # toy scoring:
    risk_grade = "B"
    pd_estimate = 0.04
    lgd_estimate = 0.45
    rec_max_exposure = avg_rev * 2 if avg_rev > 0 else 50000.0
    affordability_band = "MEDIUM"
    drivers: List[str] = []

    if score >= 80:
        risk_grade = "A"
        pd_estimate = 0.02
        drivers.append("GOOD_BUREAU_SCORE")
    elif score < 60:
        risk_grade = "C"
        pd_estimate = 0.08
        drivers.append("LOW_BUREAU_SCORE")

    if b.years_in_business is not None and b.years_in_business < 1:
        drivers.append("SHORT_OPERATING_HISTORY")

    dscr = 1.8  # just a placeholder
    debt_to_revenue = 0.25

    if not drivers:
        drivers = ["BASELINE"]

    uw = LendingUnderwriting(
        lending_application_id=app_obj.id,
        risk_grade=risk_grade,
        pd_estimate=pd_estimate,
        lgd_estimate=lgd_estimate,
        recommended_max_exposure=rec_max_exposure,
        affordability_band=affordability_band,
        key_risk_drivers=drivers,
        dscr=dscr,
        debt_to_revenue_ratio=debt_to_revenue,
    )
    db.add(uw)
    db.commit()
    db.refresh(uw)

    return RunLendingUnderwritingResponse(
        underwriting_id=uw.id,
        risk_grade=risk_grade,
        pd_estimate=float(pd_estimate),
        lgd_estimate=float(lgd_estimate),
        recommended_max_exposure=float(rec_max_exposure),
        affordability_band=affordability_band,
        key_risk_drivers=drivers,
        supporting_metrics={
            "dscr": float(dscr),
            "debt_to_revenue_ratio": float(debt_to_revenue),
        },
    )


@app.post(
    "/lending/offers/generate",
    response_model=GenerateCreditLineOffersResponse,
)
def generate_credit_line_offers(
    payload: GenerateCreditLineOffersRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)

    uw = (
        db.query(LendingUnderwriting)
        .filter(LendingUnderwriting.lending_application_id == app_obj.id)
        .order_by(LendingUnderwriting.created_at.desc())
        .first()
    )
    if not uw:
        raise HTTPException(status_code=400, detail="No underwriting result found")

    # simple rule: propose one LOC at 80% of recommended exposure
    rec = float(uw.recommended_max_exposure or 50000.0)
    limit = rec * 0.8

    offer = LendingOffer(
        lending_application_id=app_obj.id,
        offer_code=f"OFFER-LOC-{int(limit)}",
        product_type="REVOLVING_LOC",
        credit_limit=limit,
        min_credit_limit=limit * 0.5,
        max_credit_limit=rec,
        apr=0.14,
        annual_fee=0.0,
        origination_fee=0.01,
        tenor_months=None,
        repayment_terms="REVOLVING",
        collateral_required=False,
        notes="Based on your revenue and bureau data.",
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    return GenerateCreditLineOffersResponse(
        offers=[
            Offer(
                offer_id=offer.id,
                product_type=offer.product_type,
                credit_limit=float(offer.credit_limit),
                min_credit_limit=float(offer.min_credit_limit)
                if offer.min_credit_limit is not None
                else None,
                max_credit_limit=float(offer.max_credit_limit)
                if offer.max_credit_limit is not None
                else None,
                apr=float(offer.apr) if offer.apr is not None else None,
                annual_fee=float(offer.annual_fee)
                if offer.annual_fee is not None
                else None,
                origination_fee=float(offer.origination_fee)
                if offer.origination_fee is not None
                else None,
                tenor_months=offer.tenor_months,
                repayment_terms=offer.repayment_terms,
                collateral_required=bool(offer.collateral_required),
                notes=offer.notes,
            )
        ]
    )


@app.post(
    "/lending/offers/select",
    response_model=SelectCreditOfferResponse,
)
def select_credit_offer_for_application(
    payload: SelectCreditOfferRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)
    offer = (
        db.query(LendingOffer)
        .filter(
            LendingOffer.id == payload.offer_id,
            LendingOffer.lending_application_id == app_obj.id,
        )
        .first()
    )
    if not offer:
        raise HTTPException(
            status_code=404, detail="Offer not found for this application"
        )

    offer_model = Offer(
        offer_id=offer.id,
        product_type=offer.product_type,
        credit_limit=float(offer.credit_limit),
        min_credit_limit=float(offer.min_credit_limit)
        if offer.min_credit_limit is not None
        else None,
        max_credit_limit=float(offer.max_credit_limit)
        if offer.max_credit_limit is not None
        else None,
        apr=float(offer.apr) if offer.apr is not None else None,
        annual_fee=float(offer.annual_fee) if offer.annual_fee is not None else None,
        origination_fee=float(offer.origination_fee)
        if offer.origination_fee is not None
        else None,
        tenor_months=offer.tenor_months,
        repayment_terms=offer.repayment_terms,
        collateral_required=bool(offer.collateral_required),
        notes=offer.notes,
    )

    return SelectCreditOfferResponse(
        status="OFFER_SELECTED",
        selected_offer_snapshot=offer_model,
    )


@app.post(
    "/lending/facility/open",
    response_model=OpenCreditFacilityResponse,
)
def open_credit_facility_from_lending_application(
    payload: OpenCreditFacilityRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)

    # if facility already exists, return it
    existing = app_obj.facilities[0] if app_obj.facilities else None
    if existing:
        return OpenCreditFacilityResponse(
            facility_id=existing.id,
            facility_type=existing.facility_type,
            customer_id=existing.customer_id,
            business_id=existing.business_id,
            account_number=existing.account_number,
            credit_limit=float(existing.credit_limit),
            apr=float(existing.apr) if existing.apr is not None else None,
            status=existing.status,
            billing_cycle_day=existing.billing_cycle_day,
            drawdown_terms=existing.drawdown_terms,
        )

    # pick any offer (here: latest one)
    offer = (
        db.query(LendingOffer)
        .filter(LendingOffer.lending_application_id == app_obj.id)
        .order_by(LendingOffer.created_at.desc())
        .first()
    )
    if not offer:
        raise HTTPException(
            status_code=400, detail="No offer available to open facility"
        )

    acc_num = "20" + str(app_obj.id).replace("-", "")[:10]
    facility = CreditFacility(
        lending_application_id=app_obj.id,
        customer_id=app_obj.customer_id,
        business_id=app_obj.business_id,
        facility_type=offer.product_type,
        account_number=acc_num,
        credit_limit=offer.credit_limit,
        apr=offer.apr,
        status="ACTIVE",
        billing_cycle_day=15,
        drawdown_terms="REVOLVING_NET_30",
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)

    return OpenCreditFacilityResponse(
        facility_id=facility.id,
        facility_type=facility.facility_type,
        customer_id=facility.customer_id,
        business_id=facility.business_id,
        account_number=facility.account_number,
        credit_limit=float(facility.credit_limit),
        apr=float(facility.apr) if facility.apr is not None else None,
        status=facility.status,
        billing_cycle_day=facility.billing_cycle_day,
        drawdown_terms=facility.drawdown_terms,
    )


@app.post(
    "/lending/decision/notify",
    response_model=SendLendingDecisionNotificationResponse,
)
def send_lending_decision_notification(
    payload: SendLendingDecisionNotificationRequest,
    db: Session = Depends(get_db),
):
    app_obj = require_lending_application(db, payload.lending_application_id)

    notif = Notification(
        context_type="LENDING_APPLICATION",
        context_id=app_obj.id,
        channel=payload.channel,
        decision=payload.decision,
        reason_codes=payload.reason_codes or [],
        delivery_status="SENT",
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    return SendLendingDecisionNotificationResponse(
        notification_id=notif.id,
        delivery_status=notif.delivery_status,
    )
