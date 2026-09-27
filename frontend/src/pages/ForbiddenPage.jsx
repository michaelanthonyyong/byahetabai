import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export default function ForbiddenPage() {
  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <div className="max-w-md text-center space-y-4" data-testid="forbidden-page">
        <div className="text-xs uppercase tracking-widest text-stone-500">403 · Forbidden</div>
        <h1 className="text-2xl font-semibold text-stone-900">You don't have access here</h1>
        <p className="text-sm text-stone-600">
          Your account doesn't have permission to view this page. Contact your admin if you think this is a mistake.
        </p>
        <Button asChild variant="outline"><Link to="/">Back home</Link></Button>
      </div>
    </div>
  );
}
