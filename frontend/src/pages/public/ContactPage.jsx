import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageShell from "@/components/public/PageShell";
import { api, formatApiError } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Mail, Phone, Send } from "lucide-react";

export default function ContactPage() {
  const [params] = useSearchParams();
  const pkgSlug = params.get("package") || "";
  const [form, setForm] = useState({
    name: "", email: "", phone: "", subject: "", message: "", package_slug: pkgSlug,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (!payload[k]) delete payload[k]; });
      await api.post("/public/contact", payload);
      setDone(true);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageShell>
      <section className="mx-auto max-w-6xl px-6 py-14 md:py-20 grid gap-10 lg:grid-cols-[1.2fr,1fr]" data-testid="contact-page">
        <div>
          <div className="text-[11px] uppercase tracking-[0.3em] text-brand-ocean mb-3">Contact</div>
          <h1 className="font-display text-4xl md:text-5xl leading-tight text-brand-ink">
            Talk to an eNaviga agent.
          </h1>
          <p className="mt-4 text-brand-ink-soft leading-relaxed max-w-xl">
            Tell us where you'd like to go and when. An agent will get back to you with
            packages, dates, and quotes tailored to your group.
          </p>

          <div className="mt-8 space-y-3 text-sm text-brand-ink-soft">
            <div className="flex items-center gap-3">
              <Mail size={18} className="text-brand-ocean" />
              <a href="mailto:hello@biyahetabaitravel.com" className="hover:text-brand-ocean">hello@biyahetabaitravel.com</a>
            </div>
            <div className="flex items-center gap-3">
              <Phone size={18} className="text-brand-ocean" />
              <span>+63 900 000 0000</span>
            </div>
          </div>

          {pkgSlug ? (
            <div className="mt-6 rounded-xl bg-brand-mist p-4 text-xs text-brand-ink-soft" data-testid="contact-package-context">
              Enquiring about package <span className="font-mono">{pkgSlug}</span>
            </div>
          ) : null}
        </div>

        <div className="rounded-3xl border border-brand-line bg-white p-6 md:p-8">
          {done ? (
            <div className="text-center py-10" data-testid="contact-success">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-mist">
                <Send className="text-brand-ocean" />
              </div>
              <h2 className="font-display text-2xl mt-4 text-brand-ink">Message sent</h2>
              <p className="mt-2 text-sm text-brand-ink-soft">
                An agent will reach out shortly. Thanks for choosing eNaviga.
              </p>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={submit} data-testid="contact-form">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name" required value={form.name} onChange={set("name")} testid="contact-name" />
                <Field label="Email" type="email" required value={form.email} onChange={set("email")} testid="contact-email" />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Phone" value={form.phone} onChange={set("phone")} testid="contact-phone" />
                <Field label="Subject" value={form.subject} onChange={set("subject")} testid="contact-subject" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-brand-ink-soft mb-1.5">
                  Message *
                </label>
                <textarea
                  required rows={5} value={form.message} onChange={set("message")}
                  data-testid="contact-message"
                  className="w-full rounded-xl border border-brand-line bg-white p-3 outline-none focus:border-brand-ocean transition-colors"
                />
              </div>
              {error ? (
                <Alert variant="destructive" data-testid="contact-error">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
              <button
                type="submit" disabled={busy}
                data-testid="contact-submit-button"
                className="w-full rounded-full bg-brand-ocean text-white font-semibold py-3 hover:bg-brand-ocean-deep transition-colors disabled:opacity-60"
              >
                {busy ? "Sending…" : "Send message"}
              </button>
            </form>
          )}
        </div>
      </section>
    </PageShell>
  );
}

function Field({ label, required, testid, ...rest }) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-wider text-brand-ink-soft mb-1.5">
        {label}{required ? " *" : ""}
      </label>
      <input
        {...rest} required={required}
        data-testid={testid}
        className="w-full rounded-xl border border-brand-line bg-white p-3 outline-none focus:border-brand-ocean transition-colors"
      />
    </div>
  );
}
