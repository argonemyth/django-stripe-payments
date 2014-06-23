import types, datetime

from django import forms
from django.utils.translation import ugettext as _

from .settings import PLAN_CHOICES

FORM_PREIX = 'stripe'
CURRENT_YEAR = datetime.date.today().year
MONTH_CHOICES = [(i, '%02d' % i) for i in xrange(1, 13)]
YEAR_CHOICES = [(i, i) for i in range(CURRENT_YEAR, CURRENT_YEAR + 10)]


def make_widget_anonymous(widget):
    def _anonymous_render(instance, name, value, attrs=None):
        return instance._orig_render('', value, attrs)

    widget._orig_render = widget.render
    widget.render = types.MethodType(_anonymous_render, widget)

    return widget


class CardForm(forms.Form):
    number = forms.CharField(label=_("Card number"), required=False)
    exp_month = forms.CharField(label=_("Expiration month"), required=False, widget=forms.Select(choices=MONTH_CHOICES))
    exp_year = forms.CharField(label=_("Expiration year"), required=False, widget=forms.Select(choices=YEAR_CHOICES))

    def get_cvc_field(self):
        return forms.CharField(label=_("Security code (CVC)"), required=False)


    def __init__(self, validate_cvc=True, validate_address=False, \
                    prefix=FORM_PREIX, *args, **kwargs):
        super(CardForm, self).__init__(prefix=prefix, *args, **kwargs)

        if validate_cvc:
            self.fields['cvc'] = self.get_cvc_field()


class AnonymousCardForm(CardForm):
    def __init__(self, *args, **kwargs):
        super(AnonymousCardForm, self).__init__(*args, **kwargs)

        for key in self.fields.keys():
            make_widget_anonymous(self.fields[key].widget)


class CardTokenForm(AnonymousCardForm):
    last4 = forms.CharField(min_length=4, max_length=4, required=False, widget=forms.HiddenInput())
    token = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, prefix=FORM_PREIX, *args, **kwargs):
        super(CardTokenForm, self).__init__(prefix=prefix, *args, **kwargs)

    def clean(self):
        if not self.cleaned_data['last4'] or not self.cleaned_data['token']:
            raise forms.ValidationError(_("Could not validate credit card."))


class PlanForm(forms.Form):
    # pylint: disable=R0924
    plan = forms.ChoiceField(choices=PLAN_CHOICES + [("", "-------")])


class SubscriptionForm(CardTokenForm):
    plan = forms.CharField(required=False, widget=forms.HiddenInput())
    accepted_terms = forms.BooleanField(required=False)

    def __init__(self, prefix="stripe", *args, **kwargs):
        super(SubscriptionForm, self).__init__(prefix=prefix, *args, **kwargs)

    def clean(self):
        #super(SubscriptionForm, self).clean()
        #logger.debug(self.cleaned_data)
        if not self.cleaned_data['accepted_terms']:
            raise forms.ValidationError('Please review the Privacy Policy and Terms and Conditions.')

        if not self.cleaned_data['plan']: 
            raise forms.ValidationError("Please select a Subscription Plan.")

        if self.cleaned_data['plan'] != 'free' and (not self.cleaned_data['last4'] or not self.cleaned_data['token']):
            raise forms.ValidationError("Could not validate credit card.")

        return self.cleaned_data

    def save(self, user):
        #logger.debug(user)
        try:
            customer = stripe.Customer.create(
                #description=self.get_customer_description(user),
                card=self.cleaned_data['token'],
                plan=self.cleaned_data['plan'],
                email=user.email,
            )   
            error = None
        except stripe.CardError as e:
            logger.debug("Card Error: %s" % e)
            error = e 
            customer = None

        return (customer, error)
