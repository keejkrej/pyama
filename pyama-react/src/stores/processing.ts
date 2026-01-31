import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, type MicroscopyMetadata, type AvailableFeatures } from "../lib/api";

export interface SchemaProperty {
  type: string;
  default?: unknown;
  description?: string;
}

export interface PcChannelEntry {
  channel: number;
  feature: string;
}

export interface FlChannelEntry {
  channel: number;
  feature: string;
}

interface ProcessingState {
  // Microscopy file state
  microscopyFile: string;
  microscopyMetadata: MicroscopyMetadata | null;
  metadataLoading: boolean;

  // Channel configuration
  pcEntries: PcChannelEntry[];
  flEntries: FlChannelEntry[];

  // Available features (fetched from backend)
  availableFeatures: AvailableFeatures | null;
  featuresLoading: boolean;

  // Output configuration
  outputDir: string;

  // Parameters
  manualParams: boolean;
  params: Record<string, unknown>;

  // Schema (fetched from backend)
  paramsSchema: Record<string, SchemaProperty> | null;
  schemaLoading: boolean;

  // Actions
  setMicroscopyFile: (file: string) => void;
  setMicroscopyMetadata: (metadata: MicroscopyMetadata | null) => void;
  setMetadataLoading: (loading: boolean) => void;
  setPcEntries: (entries: PcChannelEntry[]) => void;
  setFlEntries: (entries: FlChannelEntry[]) => void;
  setAvailableFeatures: (features: AvailableFeatures | null) => void;
  setFeaturesLoading: (loading: boolean) => void;
  setOutputDir: (dir: string) => void;
  setManualParams: (manual: boolean) => void;
  setParams: (params: Record<string, unknown>) => void;
  setParamsSchema: (schema: Record<string, SchemaProperty> | null) => void;
  setSchemaLoading: (loading: boolean) => void;
  resetProcessing: () => void;
  fetchFeatures: () => Promise<void>;
  fetchSchema: () => Promise<void>;
}

export const useProcessingStore = create<ProcessingState>()(
  persist(
    (set, get) => ({
      // Initial state
      microscopyFile: "",
      microscopyMetadata: null,
      metadataLoading: false,
      pcEntries: [],
      flEntries: [],
      availableFeatures: null,
      featuresLoading: false,
      outputDir: "",
      manualParams: true,
      params: {},
      paramsSchema: null,
      schemaLoading: false,

      // Actions
      setMicroscopyFile: (file) => set({ microscopyFile: file }),
      setMicroscopyMetadata: (metadata) => set({ microscopyMetadata: metadata }),
      setMetadataLoading: (loading) => set({ metadataLoading: loading }),
      setPcEntries: (entries) => set({ pcEntries: entries }),
      setFlEntries: (entries) => set({ flEntries: entries }),
      setAvailableFeatures: (features) => set({ availableFeatures: features }),
      setFeaturesLoading: (loading) => set({ featuresLoading: loading }),
      setOutputDir: (dir) => set({ outputDir: dir }),
      setManualParams: (manual) => set({ manualParams: manual }),
      setParams: (params) => set({ params }),
      setParamsSchema: (schema) => set({ paramsSchema: schema }),
      setSchemaLoading: (loading) => set({ schemaLoading: loading }),

      resetProcessing: () =>
        set({
          microscopyFile: "",
          microscopyMetadata: null,
          metadataLoading: false,
          pcEntries: [],
          flEntries: [],
          outputDir: "",
          manualParams: true,
          params: {},
        }),

      fetchFeatures: async () => {
        const { availableFeatures } = get();
        if (availableFeatures) return; // Already cached

        set({ featuresLoading: true });
        try {
          const features = await api.getFeatures();
          set({ availableFeatures: features });
        } catch (err) {
          console.warn("Failed to fetch features:", err);
        } finally {
          set({ featuresLoading: false });
        }
      },

      fetchSchema: async () => {
        const { paramsSchema } = get();
        if (paramsSchema) return; // Already cached

        set({ schemaLoading: true });
        try {
          const schema = await api.getConfigSchema();
          const schemaAny = schema as Record<string, unknown>;

          // Handle $ref - Pydantic uses $defs for nested models
          let paramsProps = (schemaAny?.properties as Record<string, unknown>)
            ?.params as Record<string, unknown> | undefined;
          let properties = paramsProps?.properties as
            | Record<string, SchemaProperty>
            | undefined;

          if (!properties && paramsProps?.$ref) {
            const refPath = paramsProps.$ref as string;
            const refName = refPath.split("/").pop();
            const defs = schemaAny?.$defs as Record<string, unknown> | undefined;
            properties = (defs?.[refName as string] as Record<string, unknown>)
              ?.properties as Record<string, SchemaProperty> | undefined;
          }

          if (properties) {
            set({ paramsSchema: properties });

            // Merge schema defaults with existing params
            const currentParams = get().params;
            const merged: Record<string, unknown> = {};
            for (const [key, prop] of Object.entries(properties)) {
              if (currentParams[key] !== undefined && currentParams[key] !== "") {
                merged[key] = currentParams[key];
              } else if (prop.default !== undefined) {
                merged[key] = prop.default;
              }
            }
            set({ params: merged });
          }
        } catch (err) {
          console.warn("Failed to fetch config schema:", err);
        } finally {
          set({ schemaLoading: false });
        }
      },
    }),
    {
      name: "pyama:processing",
      // Only persist certain fields, not loading states
      partialize: (state) => ({
        microscopyFile: state.microscopyFile,
        microscopyMetadata: state.microscopyMetadata,
        pcEntries: state.pcEntries,
        flEntries: state.flEntries,
        availableFeatures: state.availableFeatures,
        outputDir: state.outputDir,
        manualParams: state.manualParams,
        params: state.params,
        paramsSchema: state.paramsSchema,
      }),
    }
  )
);
