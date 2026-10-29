import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { CustomerDialog } from "@/components/agent/CustomerDialog";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Search, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

const Row = ({ c, onEdit, onDelete }) => (
  <TableRow data-testid={`customer-row-${c.id}`}>
    <TableCell className="font-medium">{c.full_name}</TableCell>
    <TableCell className="text-stone-600">{c.email || "—"}</TableCell>
    <TableCell className="text-stone-600 whitespace-nowrap">{c.phone || "—"}</TableCell>
    <TableCell className="text-center" data-testid={`customer-bookings-${c.id}`}>{c.bookings_count}</TableCell>
    <TableCell className="text-right whitespace-nowrap">
      <Button variant="ghost" size="sm" onClick={() => onEdit(c)} data-testid={`customer-edit-${c.id}`}><Pencil size={14} /></Button>
      <Button variant="ghost" size="sm" onClick={() => onDelete(c)} disabled={c.bookings_count > 0} title={c.bookings_count ? "Has bookings" : "Delete"} data-testid={`customer-delete-${c.id}`}><Trash2 size={14} /></Button>
    </TableCell>
  </TableRow>
);

export default function AgentCustomersPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["agent-customers"],
    queryFn: () => api.get("/agent/customers").then((r) => r.data.customers),
  });
  const rows = (data || []).filter((c) =>
    !q || [c.full_name, c.email, c.phone].some((v) => v && v.toLowerCase().includes(q.toLowerCase())));

  const remove = async () => {
    try {
      await api.delete(`/agent/customers/${deleting.id}`);
      toast.success("Customer deleted.");
      qc.invalidateQueries({ queryKey: ["agent-customers"] });
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setDeleting(null);
  };

  return (
    <AgentShell subtitle="Clients" title="Customers"
      actions={<Button onClick={() => setEditing({})} className="bg-teal-800 hover:bg-teal-900" data-testid="customer-new-button"><Plus size={14} className="mr-1" />New customer</Button>}>
      <div className="max-w-5xl space-y-4">
        <div className="relative sm:w-80">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email, phone" className="pl-8" data-testid="customer-search" />
        </div>
        <Card className="border-stone-200"><CardContent className="p-0 overflow-x-auto">
          <Table data-testid="customers-table">
            <TableHeader><TableRow>
              <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Phone</TableHead>
              <TableHead className="text-center">Bookings</TableHead><TableHead />
            </TableRow></TableHeader>
            <TableBody>
              {isLoading ? null : rows.length === 0 ? (
                <TableRow><TableCell colSpan={5} className="text-center py-10 text-stone-500" data-testid="customers-empty">No customers yet.</TableCell></TableRow>
              ) : rows.map((c) => <Row key={c.id} c={c} onEdit={setEditing} onDelete={setDeleting} />)}
            </TableBody>
          </Table>
        </CardContent></Card>
      </div>
      {editing ? <CustomerDialog customer={editing.id ? editing : null} onClose={() => setEditing(null)} /> : null}
      <AlertDialog open={!!deleting} onOpenChange={(o) => { if (!o) setDeleting(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting?.full_name}?</AlertDialogTitle>
            <AlertDialogDescription>This can't be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="customer-delete-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={remove} className="bg-red-600 hover:bg-red-700" data-testid="customer-delete-confirm">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AgentShell>
  );
}
