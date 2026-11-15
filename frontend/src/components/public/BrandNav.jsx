import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

import BrandLogo from "@/components/BrandLogo";
const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/packages", label: "Tours" },
  { to: "/destinations", label: "Destinations" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

export default function BrandNav({ transparent = false }) {
  const { user } = useAuth();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!transparent) return;
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [transparent]);

  useEffect(() => { setOpen(false); }, [location.pathname]);

  const solid = !transparent || scrolled || open;

  const portalHref =
    user && user.role === "admin" ? "/admin" :
    user && user.role === "agent" ? "/agent" : null;

  return (
    <header
      data-testid="brand-nav"
      className={[
        "fixed inset-x-0 top-0 z-40 transition-colors duration-300",
        solid ? "bg-brand-cream/95 backdrop-blur border-b border-brand-line" : "bg-transparent border-b border-transparent",
      ].join(" ")}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 md:py-5">
        <Link to="/" className="flex items-center" data-testid="brand-logo-link" aria-label="eNaviga home">
          <BrandLogo className="h-8 md:h-10" onDark={!solid} />
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV.map((item) => (
            <NavLink
              key={item.to} to={item.to} end={item.end}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={({ isActive }) =>
                [
                  "text-sm font-medium tracking-wide transition-colors",
                  solid
                    ? (isActive ? "text-brand-ocean" : "text-brand-ink-soft hover:text-brand-ocean")
                    : (isActive ? "text-white" : "text-white/80 hover:text-white"),
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          {portalHref ? (
            <Link
              to={portalHref} data-testid="nav-portal-link"
              className={[
                "text-sm font-medium px-4 py-2 rounded-full transition-colors",
                solid ? "bg-brand-ocean text-white hover:bg-brand-ocean-deep"
                      : "bg-white text-brand-ocean hover:bg-brand-cream",
              ].join(" ")}
            >
              My portal
            </Link>
          ) : (
            <Link
              to="/login" data-testid="nav-login-link"
              className={[
                "text-sm font-medium px-4 py-2 rounded-full transition-colors",
                solid ? "bg-brand-ocean text-white hover:bg-brand-ocean-deep"
                      : "bg-white text-brand-ocean hover:bg-brand-cream",
              ].join(" ")}
            >
              Agent login
            </Link>
          )}
        </div>

        <button
          className={["md:hidden inline-flex items-center justify-center rounded-full p-2",
            solid ? "text-brand-ink" : "text-white"].join(" ")}
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
          data-testid="nav-mobile-toggle"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open ? (
        <div className="md:hidden bg-brand-cream border-t border-brand-line" data-testid="nav-mobile-panel">
          <div className="px-6 py-4 flex flex-col gap-3">
            {NAV.map((item) => (
              <NavLink
                key={item.to} to={item.to} end={item.end}
                className={({ isActive }) =>
                  ["py-2 text-base",
                   isActive ? "text-brand-ocean font-semibold" : "text-brand-ink"].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
            <Link
              to={portalHref || "/login"}
              className="mt-2 inline-flex items-center justify-center rounded-full bg-brand-ocean px-4 py-2 text-sm font-medium text-white"
            >
              {portalHref ? "My portal" : "Agent login"}
            </Link>
          </div>
        </div>
      ) : null}
    </header>
  );
}
