"use client";

import React, { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, submitHomeCitySelection } from "../../../lib/api/bootstrap";
import { LegalLinks } from "../../LegalLinks";

type CitySelectionFormProps = {
  authToken: string;
  cityIds: string[];
};

export function CitySelectionForm({
  authToken,
  cityIds,
}: CitySelectionFormProps) {
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
      router.replace(`/meetings?refresh=${Date.now()}`);
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
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <section className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-xl shadow-slate-200/60 backdrop-blur">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-700">Onboarding</p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Select your home city</h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-600">
            Choose the city you want to follow so CouncilSense can personalize meeting summaries and alerts.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-8 space-y-5">
          <label htmlFor="home-city" className="block text-sm font-medium text-slate-700">
            Home city
          </label>
        <select
          id="home-city"
          name="home-city"
          value={selectedCityId}
          onChange={(event) => setSelectedCityId(event.target.value)}
          disabled={isSubmitting}
          className="mt-2 block w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
        >
          {cityOptions.map((option) => (
            <option key={option.cityId} value={option.cityId}>
              {option.label}
            </option>
          ))}
        </select>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center justify-center rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSubmitting ? "Saving..." : "Continue"}
            </button>
            <p className="text-sm text-slate-500">You can change this later in settings.</p>
          </div>
        </form>

        {submitError ? (
          <p role="alert" className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {submitError}
          </p>
        ) : null}

        <div className="mt-8 border-t border-slate-200 pt-6">
          <LegalLinks label="Onboarding legal links" />
        </div>
      </section>
    </main>
  );
}
