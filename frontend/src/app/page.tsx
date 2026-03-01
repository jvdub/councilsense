import React from "react";
import Link from "next/link";

export default function LandingPage() {
  return (
    <main>
      <h1>CouncilSense</h1>
      <p>Stay informed about your local government meetings.</p>
      <p>
        <Link href="/meetings">Go to meetings</Link>
      </p>
    </main>
  );
}