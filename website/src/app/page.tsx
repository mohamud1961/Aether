import { HeroSection } from "@/components/sections/HeroSection";
import { ImpactEconomicsSection } from "@/components/sections/ImpactEconomicsSection";
import { ExperimentFactorySection } from "@/components/sections/ExperimentFactorySection";
import { CapabilitiesSection } from "@/components/sections/CapabilitiesSection";
import { ArchitectureSection } from "@/components/sections/ArchitectureSection";
import { UseCasesSection } from "@/components/sections/UseCasesSection";
import { DoctrineSection } from "@/components/sections/DoctrineSection";
import { CTASection } from "@/components/sections/CTASection";

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-black w-full overflow-x-hidden selection:bg-indigo-500/20 dark:selection:bg-indigo-400/30 selection:text-indigo-900 dark:selection:text-indigo-100">
      <HeroSection />
      <ImpactEconomicsSection />
      <ExperimentFactorySection />
      <CapabilitiesSection />
      <ArchitectureSection />
      <UseCasesSection />
      <DoctrineSection />
      <CTASection />
    </main>
  );
}
