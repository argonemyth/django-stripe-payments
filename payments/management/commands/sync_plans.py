import decimal

from django.conf import settings
from django.core.management.base import BaseCommand

import stripe

from payments.models import Plan 


class Command(BaseCommand):

    help = "Sync your plans"

    def handle(self, *args, **options):
        """
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_plans = stripe.Plan.all()['data']
        for plan in stripe_plans:
            print plan
        """
        plans = Plan.objects.all()
        if plans:
            for plan in plans:
                plan.update_or_create()
        else:
            print "You haven't created any plan."
