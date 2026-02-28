"use client";

import React, { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, submitHomeCitySelection } from "../../../lib/api/bootstrap";
import { LegalLinks } from "../../LegalLinks";

type CitySelectionFormProps = {
  authToken: string;
  cityIds: string[];
};

export function CitySelectionForm({ authToken, cityIds }: CitySelectionFormProps) {
  const router = useRouter();
  const [selectedCityId, setSelectedCityId] = useState(cityIds[0] ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const cityOptions = useMemo(
    () => cityIds.map((cityId) => ({ cityId, label: cityId })),
    [cityIds],
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedCityId) {
      setSubmitError("Select a city to continue.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await submitHomeCitySelection(authToken, selectedCityId);
      router.push("/meetings");
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setSubmitError("Selected city is not supported.");
      } else {
        setSubmitError("Unable to save your city. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Select your home city</h1>
      <form onSubmit={onSubmit}>
        <label htmlFor="home-city">Home city</label>
        <select
          id="home-city"
          name="home-city"
          value={selectedCityId}
          onChange={(event) => setSelectedCityId(event.target.value)}
          disabled={isSubmitting}
        >
          {cityOptions.map((option) => (
            <option key={option.cityId} value={option.cityId}>
              {option.label}
            </option>
          ))}
        </select>

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Continue"}
        </button>
      </form>
      <LegalLinks label="Onboarding legal links" />
      {submitError ? <p role="alert">{submitError}</p> : null}
    </main>
  );
}