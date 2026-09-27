import BrandNav from "./BrandNav";
import BrandFooter from "./BrandFooter";

/**
 * Standard public-site frame.
 * Use `heroTransparent` on pages whose hero image should sit under the nav.
 */
export default function PageShell({ children, heroTransparent = false }) {
  return (
    <div className="brand-scope min-h-screen flex flex-col bg-brand-cream text-brand-ink">
      <BrandNav transparent={heroTransparent} />
      <main className={heroTransparent ? "" : "pt-24 md:pt-28"}>{children}</main>
      <BrandFooter />
    </div>
  );
}
