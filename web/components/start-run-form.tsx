import { Button } from "@/components/ui/button";
import { startRunAction } from "@/app/actions";

export function StartRunForm() {
  return (
    <form action={startRunAction}>
      <Button type="submit" size="sm">
        Start new run
      </Button>
    </form>
  );
}
