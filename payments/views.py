import json

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic import FormView 
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render_to_response

import stripe

from . import settings as app_settings
from .forms import PlanForm, CardTokenForm
from .models import (
    Customer,
    CurrentSubscription,
    Event,
    EventProcessingException,
    Plan,
    CreditBundle
)


class PaymentsContextMixin(object):

    def get_context_data(self, **kwargs):
        context = super(PaymentsContextMixin, self).get_context_data(**kwargs)
        context.update({
            "STRIPE_PUBLIC_KEY": app_settings.STRIPE_PUBLIC_KEY,
            "PLAN_CHOICES": app_settings.PLAN_CHOICES,
            "PAYMENT_PLANS": app_settings.PAYMENTS_PLANS
        })
        return context


class SinglePaymentContextMixin(object):

    def get_context_data(self, **kwargs):
        context = super(SinglePaymentContextMixin, self).get_context_data(**kwargs)
        context.update({
            "STRIPE_PUBLIC_KEY": app_settings.STRIPE_PUBLIC_KEY,
        })
        return context


def _ajax_response(request, template, **kwargs):
    response = {
        "html": render_to_string(
            template,
            RequestContext(request, kwargs)
        )
    }
    if "location" in kwargs:
        response.update({"location": kwargs["location"]})
    if "bundle" in kwargs:
        response.update({"bundle": kwargs["bundle"]})

    return HttpResponse(json.dumps(response), content_type="application/json")


class SubscribePlanView(PaymentsContextMixin, DetailView):
    model = Plan
    context_object_name = 'plan'
    template_name = "payments/subscribe_plan.html"

    def get_context_data(self, **kwargs):
        context = super(SubscribePlanView, self).get_context_data(**kwargs)
        context.update({
            "form": CardTokenForm()
        }) 
        return context
        

class SubscribeView(PaymentsContextMixin, ListView):
    model = Plan
    template_name = "payments/subscribe.html"

"""
class ChangeCardView(PaymentsContextMixin, TemplateView):
    template_name = "payments/change_card.html"
"""

class CancelView(PaymentsContextMixin, TemplateView):
    template_name = "payments/cancel.html"


class ChangePlanView(PaymentsContextMixin, TemplateView):
    template_name = "payments/change_plan.html"

    def get_context_data(self, **kwargs):
        context = super(ChangePlanView, self).get_context_data(**kwargs)
        plan = kwargs['plan']
        print plan
        if plan == 'free':
            new_plan = {}
            new_plan['name'] = plan 
        else:
            new_plan = Plan.objects.get(stripe_plan_id=plan)
        context.update({
            "plan": new_plan 
        })
        return context


class HistoryView(PaymentsContextMixin, TemplateView):
    template_name = "payments/history.html"


@require_POST
@login_required
def change_card(request):
    try:
        customer = request.user.customer
        send_invoice = customer.card_fingerprint == ""
        customer.update_card(
            request.POST.get("stripe_token")
        )
        if send_invoice:
            customer.send_invoice()
        customer.retry_unpaid_invoices()
        data = {}
    except stripe.CardError, e:
        data = {"error": e.message}
    return _ajax_response(request, "payments/_change_card_form.html", **data)


#@require_POST
@login_required
def change_card_with_form(request):
    if request.POST:
        # process the token returned by stripe.js
        try:
            customer = request.user.customer
            customer.update_card(
                request.POST.get("stripe_token")
            )
            messages.success = 'Your credit card info has been successfully changed.'
        except stripe.CardError, e:
            try:
                messages.error(request, "%s" % e.args[0])
            except IndexError:
                messages.error(request, "Unknown error")

        return HttpResponseRedirect(reverse('payments_subscribe'))
    else:
        # Render the template that contains the form. 
        context = {
            "STRIPE_PUBLIC_KEY": app_settings.STRIPE_PUBLIC_KEY,
        }
        return render_to_response('payments/change_card.html',
                                   context,
                                   context_instance=RequestContext(request))



'''
@require_POST
@login_required
def change_plan(request):
    form = PlanForm(request.POST)
    try:
        current_plan = request.user.customer.current_subscription.plan
    except CurrentSubscription.DoesNotExist:
        current_plan = None
    if form.is_valid():
        try:
            request.user.customer.subscribe(form.cleaned_data["plan"])
            data = {
                "form": PlanForm(initial={"plan": form.cleaned_data["plan"]})
            }
        except stripe.StripeError, e:
            data = {
                "form": PlanForm(initial={"plan": current_plan}),
                "error": e.message
            }
    else:
        data = {
            "form": form
        }
    return _ajax_response(request, "payments/_change_plan_form.html", **data)
'''

#@require_POST
@login_required
def change_plan(request, plan):
    """
    plan should the the stripe_plan_id for the new plan the user want to subscribe
    """
    try:
        current_plan = request.user.customer.current_subscription.plan
    except CurrentSubscription.DoesNotExist:
        current_plan = None
    plan = Plan.objects.get(stripe_plan_id=plan)
    print "Going to change to: %s " % plan
    if plan.name != current_plan:
        try:
            request.user.customer.subscribe(plan.stripe_plan_id)
            data = {
                "message": "Plan has been successfully changed to %s" % plan.name 
            }
        except stripe.StripeError, e:
            data = {
                "error": e.message
            }
    else:
        data = {
            "error": "you should not be here, no plan change needed" 
        }
    return _ajax_response(request, "payments/_action_response.html", **data)


@require_POST
@login_required
def subscribe(request, form_class=PlanForm):
    data = {"plans": settings.PAYMENTS_PLANS}
    form = form_class(request.POST)
    if form.is_valid():
        try:
            try:
                customer = request.user.customer
            except ObjectDoesNotExist:
                customer = Customer.create(request.user)
            customer.update_card(request.POST.get("stripe_token"))
            customer.subscribe(form.cleaned_data["plansan"])
            data["form"] = form_class()
            data["location"] = reverse("payments_history")
        except stripe.StripeError as e:
            data["form"] = form
            try:
                data["error"] = e.args[0]
            except IndexError:
                data["error"] = "Unknown error"
    else:
        data["error"] = form.errors
        data["form"] = form
    return _ajax_response(request, "payments/_subscribe_form.html", **data)

@require_POST
@login_required
def subscribe_plan(request):
    data = {"plans": settings.PAYMENTS_PLANS}
    try:
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            customer = Customer.create(request.user)
        customer.update_card(request.POST.get("stripe_token"))
        print "Going to subscribe: ", request.POST.get("plan")
        customer.subscribe(request.POST.get("plan"))
        data["message"] = 'Your are now %s members!' % request.POST.get("plan")
        #data["form"] = form_class()
        data["location"] = reverse("payments_history")
    except stripe.StripeError as e:
        #data["form"] = form
        try:
            data["error"] = e.args[0]
        except IndexError:
            data["error"] = "Unknown error"

    return _ajax_response(request, "payments/_payment_form.html", **data)


@require_POST
@login_required
def payment_subscribe(request):
    """
    New plan subscription payment with a new credit card.
    """
    try:
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            customer = Customer.create(request.user)
        customer.update_card(request.POST.get("stripe_token"))
        plan = request.POST.get("plan")
        print "Going to subscribe: ", plan
        customer.subscribe(plan)
        messages.success(request, "Your are now %s members!" % plan)
        #data["form"] = form_class()
        #data["location"] = reverse("payments_history")
    except stripe.StripeError as e:
        #data["form"] = form
        try:
            messages.error(request, "%s" % e.args[0])
        except IndexError:
            messages.error(request, "Unknown error")

    return HttpResponseRedirect(reverse('userena_profile_detail', args=(request.user.username, )))
    #return _ajax_response(request, "payments/_payment_form.html", **data)


@require_POST
@login_required
def cancel(request):
    try:
        request.user.customer.cancel()
        data = {}
    except stripe.StripeError, e:
        data = {"error": e.message}
    return _ajax_response(request, "payments/_cancel_form.html", **data)


@csrf_exempt
@require_POST
def webhook(request):
    data = json.loads(request.body)
    if Event.objects.filter(stripe_id=data["id"]).exists():
        EventProcessingException.objects.create(
            data=data,
            message="Duplicate event record",
            traceback=""
        )
    else:
        event = Event.objects.create(
            stripe_id=data["id"],
            kind=data["type"],
            livemode=data["livemode"],
            webhook_message=data
        )
        event.validate()
        event.process()
    return HttpResponse()


class CreditBundleListView(SinglePaymentContextMixin, ListView):
    """
    A list of credit bundles for users to choose from. 
    """
    #queryset = User.objects.filter(is_active__exact=False).filter(my_profile__role__exact=1)
    model = CreditBundle
    template_name = 'payments/credit_bundles.html'
    context_object_name = 'bundles' 
    #paginate_by = 10

    """
    def get(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied

        return super(PendingCompanyList, self).get(request, *args, **kwargs)
    """

#@require_POST
@login_required
def purchase_credits(request, bundle):
    bundle = CreditBundle.objects.get(slug=bundle)
    data = {}
    if bundle:
        data['bundle'] = bundle.name
        try:
            try:
                customer = request.user.customer
            except ObjectDoesNotExist:
                """
                Usually, this would not happen.
                """
                customer = Customer.create(request.user)
            #print "Update card info: %s" % customer
            #customer.update_card(request.POST.get("stripe_token"))
            #customer.update_card(request.POST.get("stripeToken"))
            print "Charge %s for %s" % (customer, bundle.name)
            customer.charge(bundle.price, bundle.currency, bundle.description)
            user_account = request.user.get_profile()
            user_account.add_credits(bundle.credits)
        except stripe.StripeError as e:
            try:
                data["error"] = e.args[0]
            except IndexError:
                data["error"] = "Unknown error"
    else:
        data["error"] = "Are you sure you selected the right bundle?" 
    return _ajax_response(request, "payments/_purchase_credits.html", **data)


@login_required
def credit_bundle_purchase(request, bundle):
    bundle = CreditBundle.objects.get(slug=bundle)
    if request.POST:
        # Form submit - for customers without credit card on file.
        # process the token returned by stripe.js
        try:
            customer = request.user.customer
            customer.update_card(
                request.POST.get("stripe_token")
            )
            print "Charge %s for %s" % (customer, bundle.name)
            customer.charge(bundle.price, bundle.currency, bundle.description)
            user_account = request.user.get_profile()
            user_account.add_credits(bundle.credits)
            payment_result = 'Thanks for purchase %s, you now have\
                             %s credits.' % (
                                bundle.name,
                                request.user.get_profile().credits
                             )
        except stripe.CardError, e:
            try:
                #messages.error(request, "%s" % e.args[0])
                payment_result = "%s" % e.args[0]
            except IndexError:
                #messages.error(request, "Unknown error")
                payment_result = "Unknown error"

        context = {
            "STRIPE_PUBLIC_KEY": app_settings.STRIPE_PUBLIC_KEY,
            "payment_result": payment_result
        }
        #return HttpResponseRedirect(reverse('payments_subscribe'))
    else:
        # Render the template that contains the form. 
        context = {
            "STRIPE_PUBLIC_KEY": app_settings.STRIPE_PUBLIC_KEY,
            "bundle": bundle
        }

    return render_to_response('payments/credit_bundle_purchase.html',
                               context,
                               context_instance=RequestContext(request))
