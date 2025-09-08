from django.test import TestCase
from mt5_integration.models.liquidity_sweep import LiquiditySweep
from mt5_integration.models.trading_session import TradingSession
from django.utils import timezone

class LiquiditySweepModelTest(TestCase):
    def setUp(self):
        self.session = TradingSession.objects.create(
            session_date=timezone.now().date(),
            session_type='ASIAN',
            current_state='IDLE'
        )

    def test_liquidity_sweep_creation(self):
        sweep = LiquiditySweep.objects.create(
            session=self.session,
            symbol='XAUUSD',
            sweep_direction='UP',
            sweep_price=1950.0,
            sweep_threshold=10.0,
            sweep_time=timezone.now()
        )
        self.assertEqual(sweep.symbol, 'XAUUSD')
        self.assertEqual(sweep.sweep_direction, 'UP')
        self.assertEqual(float(sweep.sweep_price), 1950.0)
        self.assertEqual(float(sweep.sweep_threshold), 10.0)
        self.assertEqual(sweep.session, self.session)

    def test_retest_zone_fields(self):
        sweep = LiquiditySweep.objects.create(
            session=self.session,
            symbol='XAUUSD',
            sweep_direction='DOWN',
            sweep_price=1920.0,
            sweep_threshold=12.0,
            sweep_time=timezone.now(),
            retest_zone_bottom=1915.0,
            retest_zone_top=1925.0
        )
        self.assertEqual(float(sweep.retest_zone_bottom), 1915.0)
        self.assertEqual(float(sweep.retest_zone_top), 1925.0)
