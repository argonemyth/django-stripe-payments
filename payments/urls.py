from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required

from .views import (
    CancelView,
    ChangePlanView,
    HistoryView,
    SubscribePlanView,
    SubscribeView,
    CreditBundleListView
)


urlpatterns = patterns(
    "payments.views",
    url(r"^webhook/$", "webhook", name="payments_webhook"),
    url(r"^a/subscribe/$", "subscribe", name="payments_ajax_subscribe"),
    #url(r"^a/subscribe_plan/$", "subscribe_plan", name="payments_ajax_subscribe_plan"),
    url(r"^a/subscribe_plan/$", "subscribe_plan", name="payments_ajax_subscribe_plan"),
    url(r"^a/change/card/$", "change_card", name="payments_ajax_change_card"),
    url(r"^a/change/plan/(?P<plan>[\.\w-]+)/$", "change_plan", name="payments_ajax_change_plan"),
    url(r"^a/cancel/$", "cancel", name="payments_ajax_cancel"),
    url(r"^a/purchase/(?P<bundle>[\.\w-]+)/$", "purchase_credits", name="payments_ajax_purchase_credits"),
    url(
        r"^subscribe/(?P<pk>\d+)/$",
        login_required(SubscribePlanView.as_view()),
        name="payments_subscribe_plan"
    ),
    url(
        r"^subscribe/$",
        login_required(SubscribeView.as_view()),
        name="payments_subscribe"
    ),
    url(
        r"^change/plan/(?P<plan>[\.\w-]+)/$",
        login_required(ChangePlanView.as_view()),
        name="payments_change_plan"
    ),
    url(
        r"^cancel/$",
        login_required(CancelView.as_view()),
        name="payments_cancel"
    ),
    url(
        r"^history/$",
        login_required(HistoryView.as_view()),
        name="payments_history"
    ),
    url(
        r"^credits/$",
        login_required(CreditBundleListView.as_view()),
        name="credits_purchase"
    ),
    url(r"^credits/(?P<bundle>[\.\w-]+)/$",
        "credit_bundle_purchase",
        name="payments_credit_purchase"),
    url(r"^pay/$", "payment_subscribe", name="payments_pay_subscribe"),
    url(r"^change/card/$", "change_card_with_form", name="payments_change_card"),
)
