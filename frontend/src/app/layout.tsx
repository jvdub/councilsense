import React from "react";
import type { ReactNode } from "react";

import { LegalLinks } from "./LegalLinks";

type LayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: LayoutProps) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer>
          <LegalLinks label="Public legal links" />
        </footer>
      </body>
    </html>
  );
}