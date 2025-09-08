# Generated migration for Phase 3 enhancements based on client requirements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mt5_integration', '0003_tradingsession_atr_value_and_more'),
    ]

    operations = [
        # TradingSession enhancements
        migrations.AddField(
            model_name='tradingsession',
            name='weekly_realized_r',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=8),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='week_reset_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='daily_loss_limit_r',
            field=models.DecimalField(decimal_places=2, default=2.0, max_digits=8),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='current_daily_loss_r',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=8),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='london_traversed_asia',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='ny_fresh_sweep_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='confirm_deadline',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='acceptance_outside_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='tradingsession',
            name='both_sides_swept',
            field=models.BooleanField(default=False),
        ),
        
        # Update daily trade count limit default to 2 (client spec)
        migrations.AlterField(
            model_name='tradingsession',
            name='daily_trade_count_limit',
            field=models.IntegerField(default=2),
        ),

        # LiquiditySweep enhancements
        migrations.AddField(
            model_name='liquiditysweep',
            name='threshold_from_pct',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='liquiditysweep',
            name='threshold_from_atr',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='liquiditysweep',
            name='threshold_from_floor',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='liquiditysweep',
            name='chosen_threshold_component',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='liquiditysweep',
            name='atr_h1_value',
            field=models.DecimalField(decimal_places=5, max_digits=10, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='liquiditysweep',
            name='acceptance_outside',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='liquiditysweep',
            name='both_sides_swept_flag',
            field=models.BooleanField(default=False),
        ),

        # ConfluenceCheck enhancements
        migrations.AddField(
            model_name='confluencecheck',
            name='auction_blackout',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='news_tier',
            field=models.CharField(
                choices=[('TIER1', 'Tier-1'), ('OTHER', 'Other')],
                max_length=10,
                null=True,
                blank=True
            ),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='velocity_ratio',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='trend_day_high_adx',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='h1_band_walk',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='london_traversed_asia',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='ny_requires_fresh_sweep',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='participation_filter_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='adx_timeframe',
            field=models.CharField(max_length=10, default='15m'),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='spread_threshold',
            field=models.DecimalField(decimal_places=2, default=2.0, max_digits=8),
        ),
        migrations.AddField(
            model_name='confluencecheck',
            name='failure_reasons',
            field=models.TextField(blank=True, null=True),
        ),

        # TradeSignal enhancements
        migrations.AddField(
            model_name='tradesignal',
            name='entry_method',
            field=models.CharField(
                choices=[('LIMIT', 'Limit'), ('TRIGGER', 'Trigger'), ('MARKET', 'Market')],
                default='LIMIT',
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='entry_zone_reference',
            field=models.CharField(
                choices=[
                    ('CONFIRM_BODY', 'Confirmation Body'),
                    ('OB', 'Order Block'),
                    ('FVG', 'Fair Value Gap'),
                    ('MIDPOINT', 'Asian Midpoint')
                ],
                default='CONFIRM_BODY',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='sl_pips',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='tp1_pips',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='tp2_pips',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='calculated_r',
            field=models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='micro_trigger_satisfied',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='retest_expiry_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='breakeven_moved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tradesignal',
            name='trailing_active',
            field=models.BooleanField(default=False),
        ),

        # EconomicNews enhancements for news tier classification
        migrations.AddField(
            model_name='economicnews',
            name='tier',
            field=models.CharField(
                choices=[('TIER1', 'Tier-1'), ('OTHER', 'Other')],
                default='OTHER',
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='economicnews',
            name='required_buffer_minutes',
            field=models.IntegerField(default=30),
        ),
    ]
