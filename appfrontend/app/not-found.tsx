import { Compass } from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { EmptyState } from "@/components/ui/states";

export default function NotFound() {
  return (
    <Screen title="Not found" depth="root" tabs>
      <EmptyState
        icon={<Compass size={26} />}
        title="That screen doesn’t exist"
        description="Head back to your projects and pick up where you left off."
        action="Go to projects"
        href="/chats"
      />
    </Screen>
  );
}
