/* Pricing — Live tiers from /billing/plans + Stripe checkout via /billing/checkout */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import { useBillingCheckout, useBillingPlans } from '@/lib/engine/hooks';
import { PRICING_FAQ } from '@/lib/mockData';
import { useAppStore } from '@/lib/store';
import { cn } from '@/lib/utils';
import { Check, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

export default function Pricing() {
  const { billingCycle, setBillingCycle } = useAppStore();
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);

  const plans = useBillingPlans();
  const checkout = useBillingCheckout();

  const tiers = plans.data ?? [];

  async function handleCheckout(tier: string) {
    if (tier.toLowerCase() === 'team') {
      toast.info('Contact sales@coinscopeai.com for Team pricing');
      return;
    }
    try {
      const res = await checkout.mutateAsync({
        tier: tier.toLowerCase(),
        cycle: billingCycle as 'monthly' | 'annual',
        success_url: `${window.location.origin}/pricing?checkout=success`,
        cancel_url:  `${window.location.origin}/pricing?checkout=cancel`,
      });
      if (res.url) {
        toast.success(`Redirecting to Stripe checkout (${tier}, ${billingCycle})…`);
        window.location.href = res.url;
      } else {
        toast.error(`Checkout could not be started: ${res.detail ?? 'no session URL returned'}`);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? String(err);
      toast.error(`Checkout failed: ${msg}`);
    }
  }

  return (
    <DashboardLayout>
      <PageHeader title="Pricing" subtitle="Choose the plan that fits your trading operation" />

      {/* Billing toggle */}
      <div className="flex justify-center mb-8">
        <div className="flex items-center gap-3 bg-secondary rounded-lg p-1">
          <button
            onClick={() => setBillingCycle('monthly')}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-md transition-colors',
              billingCycle === 'monthly' ? 'bg-emerald/20 text-emerald' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Monthly
          </button>
          <button
            onClick={() => setBillingCycle('annual')}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-md transition-colors',
              billingCycle === 'annual' ? 'bg-emerald/20 text-emerald' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Annual <span className="text-[10px] text-emerald ml-1">Save ~17%</span>
          </button>
        </div>
      </div>

      {/* Pricing cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-10">
        {tiers.length === 0 ? (
          <div className="col-span-full text-center text-sm text-muted-foreground py-10">
            {plans.isLoading ? 'Loading plans…' : plans.isError ? 'Could not load plans from engine.' : 'No plans configured.'}
          </div>
        ) : (
          tiers.map((tier) => {
            const highlighted = tier.tier?.toLowerCase() === 'pro';
            const badge = highlighted ? 'Most Popular' : undefined;
            // Engine only exposes a monthly price. Approximate annual at ~17% discount.
            const monthly = tier.price_usd ?? 0;
            const annual  = Math.round(monthly * 12 * 0.83);
            const price   = billingCycle === 'annual' ? annual : monthly;
            const period  = billingCycle === 'annual' ? '/yr' : '/mo';
            const cta = tier.tier?.toLowerCase() === 'team' ? 'Contact Sales' : 'Start Free Trial';

            return (
              <div
                key={tier.tier ?? tier.name}
                className={cn(
                  'rounded-lg border p-5 flex flex-col transition-all',
                  highlighted
                    ? 'border-emerald/40 bg-emerald/5 shadow-lg shadow-emerald/5'
                    : 'border-border bg-card hover:border-border/80'
                )}
              >
                {badge && (
                  <div className="flex items-center gap-1 mb-3">
                    <Sparkles className="w-3.5 h-3.5 text-emerald" />
                    <span className="text-[10px] font-semibold tracking-wider uppercase text-emerald">{badge}</span>
                  </div>
                )}

                <h3 className="text-lg font-semibold text-foreground">{tier.name}</h3>
                <p className="text-xs text-muted-foreground mt-1 mb-4">{tier.description ?? ''}</p>

                {/* Price */}
                <div className="mb-4">
                  <span className="font-mono text-3xl font-bold text-foreground tabular-nums">
                    ${price}
                  </span>
                  <span className="text-sm text-muted-foreground">{period}</span>
                  {tier.tier?.toLowerCase() === 'team' && (
                    <span className="text-xs text-muted-foreground block mt-0.5">Starting price · contact sales</span>
                  )}
                </div>

                {/* CTA */}
                <button
                  onClick={() => handleCheckout(tier.tier ?? tier.name)}
                  disabled={checkout.isPending}
                  className={cn(
                    'w-full py-2.5 rounded-md text-sm font-medium transition-colors mb-5 disabled:opacity-60',
                    highlighted
                      ? 'bg-emerald text-white hover:bg-emerald/90'
                      : 'bg-secondary text-foreground hover:bg-secondary/80 border border-border'
                  )}
                >
                  {checkout.isPending ? 'Starting checkout…' : cta}
                </button>

                {/* Features */}
                <div className="space-y-2 flex-1">
                  {(tier.features ?? []).map((feat) => (
                    <div key={feat} className="flex items-start gap-2 text-xs">
                      <Check className="w-3.5 h-3.5 text-emerald shrink-0 mt-0.5" />
                      <span className="text-muted-foreground">{feat}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* FAQ (static marketing copy) */}
      <div className="max-w-2xl mx-auto">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4 text-center">
          Frequently Asked Questions
        </h2>
        <div className="space-y-2">
          {PRICING_FAQ.map((faq, i) => (
            <div key={i} className="hud-panel">
              <button
                onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                className="w-full flex items-center justify-between p-4 text-left"
              >
                <span className="text-sm text-foreground font-medium">{faq.q}</span>
                {expandedFaq === i ? (
                  <ChevronUp className="w-4 h-4 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" />
                )}
              </button>
              {expandedFaq === i && (
                <div className="px-4 pb-4 text-xs text-muted-foreground leading-relaxed">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}
