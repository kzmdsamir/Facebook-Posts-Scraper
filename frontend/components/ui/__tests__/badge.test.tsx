import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders children with the default variant", () => {
    render(<Badge>stable</Badge>);
    expect(screen.getByText("stable")).toBeInTheDocument();
  });

  it("applies the destructive variant className", () => {
    const { container } = render(<Badge variant="destructive">failed</Badge>);
    expect(container.firstChild).toHaveClass("bg-foreground");
  });
});