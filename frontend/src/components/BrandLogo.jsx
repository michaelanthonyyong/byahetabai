/**
 * The official eNaviga platform logo (main business identity).
 *
 * Never use this for agent-specific branding — agents show their own
 * business name/logo (see components/agent/AgentBrand.jsx).
 *
 * The logo's dark-blue lettering needs a light backing, so `onDark`
 * places it on a soft white plate for photos and dark backgrounds.
 */
export const BRAND_NAME = "eNaviga";
export const BRAND_LOGO_SRC = `${process.env.PUBLIC_URL}/brand/enaviga-logo.png`;

export default function BrandLogo({ className = "h-9", onDark = false, testid = "brand-logo" }) {
  const img = (
    <img
      src={BRAND_LOGO_SRC}
      alt={BRAND_NAME}
      className={`${className} w-auto object-contain select-none`}
      draggable={false}
      data-testid={testid}
    />
  );
  if (!onDark) return img;
  return (
    <span className="inline-flex items-center rounded-xl bg-white/95 px-2.5 py-1.5 shadow-sm">
      {img}
    </span>
  );
}
