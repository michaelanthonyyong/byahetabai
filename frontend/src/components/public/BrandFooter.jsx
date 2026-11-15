import { Link } from "react-router-dom";

import BrandLogo from "@/components/BrandLogo";
export default function BrandFooter() {
  return (
    <footer className="bg-brand-ocean-deep text-brand-cream" data-testid="brand-footer">
      <div className="mx-auto max-w-7xl px-6 py-14 grid gap-12 md:grid-cols-4">
        <div className="md:col-span-2 space-y-4">
          <BrandLogo className="h-11" onDark testid="footer-brand-logo" />
          <p className="text-sm text-brand-cream/70 max-w-md leading-relaxed">
            Local and international tours curated for Filipino travellers. Book a package, message an agent,
            and let us take care of the rest.
          </p>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-brand-sunset-soft mb-4">Explore</div>
          <ul className="space-y-2 text-sm">
            <li><Link to="/packages?scope=international" className="hover:text-white">International Tours</Link></li>
            <li><Link to="/packages?scope=domestic" className="hover:text-white">Domestic Tours</Link></li>
            <li><Link to="/destinations" className="hover:text-white">All Destinations</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-brand-sunset-soft mb-4">Company</div>
          <ul className="space-y-2 text-sm">
            <li><Link to="/about" className="hover:text-white">About</Link></li>
            <li><Link to="/contact" className="hover:text-white">Contact an agent</Link></li>
            <li><Link to="/login" className="hover:text-white">Agent login</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto max-w-7xl px-6 py-6 text-xs text-brand-cream/60 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>© {new Date().getFullYear()} eNaviga. All rights reserved.</div>
          <div>Go. Explore. Discover.</div>
        </div>
      </div>
    </footer>
  );
}
