import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ProjectData, TraceData } from "../lib/api";
import { api } from "../lib/api";

interface VisualizationState {
  // Persisted UI state
  dataFolder: string;
  fov: number;
  selectedFeature: string;
  currentPage: number;

  // Project data
  projectData: ProjectData | null;
  traces: TraceData[];
  totalTraces: number;
  availableFeatures: string[];
  loading: boolean;
  error: string | null;

  // Quality updates (pending save)
  qualityUpdates: Record<string, boolean>;

  // Actions
  setDataFolder: (folder: string) => void;
  setFov: (fov: number) => void;
  setSelectedFeature: (feature: string) => void;
  setCurrentPage: (page: number) => void;
  loadProject: (projectPath: string) => Promise<void>;
  loadTraces: (page?: number) => Promise<void>;
  toggleTraceQuality: (cellId: string) => void;
  saveQualityUpdates: () => Promise<void>;
  clear: () => void;
  reset: () => void;
}

export const useVisualizationStore = create<VisualizationState>()(
  persist(
    (set, get) => ({
      // Persisted UI state
      dataFolder: "",
      fov: 0,
      selectedFeature: "",
      currentPage: 0, // 0-indexed for API

      // Project data
      projectData: null,
      traces: [],
      totalTraces: 0,
      availableFeatures: [],
      loading: false,
      error: null,
      qualityUpdates: {},

      // Setters
      setDataFolder: (folder) => set({ dataFolder: folder }),
      setFov: (fov) => set({ fov, currentPage: 0 }), // Reset to first page on FOV change
      setSelectedFeature: (feature) => set({ selectedFeature: feature }),
      setCurrentPage: (page) => set({ currentPage: page }),

      // Load project
      loadProject: async (projectPath: string) => {
        set({ loading: true, error: null });
        try {
          const projectData = await api.loadVisualizationProject(projectPath);
          set({
            projectData,
            dataFolder: projectPath,
            loading: false,
            error: null,
          });
          // Auto-load traces for current FOV
          await get().loadTraces(0);
        } catch (error) {
          set({
            loading: false,
            error: error instanceof Error ? error.message : "Failed to load project",
          });
        }
      },

      // Load traces
      loadTraces: async (page?: number) => {
        const state = get();
        if (!state.projectData) {
          set({ error: "No project loaded" });
          return;
        }

        const pageToLoad = page !== undefined ? page : state.currentPage;
        set({ loading: true, error: null });

        try {
          const response = await api.getTraces(
            state.projectData.project_path,
            state.fov,
            pageToLoad,
            10, // page_size
          );

          set({
            traces: response.traces,
            totalTraces: response.total,
            currentPage: response.page,
            availableFeatures: response.features,
            loading: false,
            error: null,
          });

          // Auto-select first feature if none selected
          if (!state.selectedFeature && response.features.length > 0) {
            set({ selectedFeature: response.features[0] });
          }
        } catch (error) {
          set({
            loading: false,
            error: error instanceof Error ? error.message : "Failed to load traces",
          });
        }
      },

      // Toggle trace quality
      toggleTraceQuality: (cellId: string) => {
        const state = get();
        const trace = state.traces.find((t) => t.cell_id === cellId);
        if (!trace) return;

        const newQuality = !trace.quality;
        const updates = { ...state.qualityUpdates, [cellId]: newQuality };

        // Update local trace state
        const updatedTraces = state.traces.map((t) =>
          t.cell_id === cellId ? { ...t, quality: newQuality } : t,
        );

        set({ qualityUpdates: updates, traces: updatedTraces });
      },

      // Save quality updates
      saveQualityUpdates: async () => {
        const state = get();
        if (!state.projectData || Object.keys(state.qualityUpdates).length === 0) {
          return;
        }

        set({ loading: true, error: null });
        try {
          await api.updateTraceQuality(
            state.projectData.project_path,
            state.fov,
            state.qualityUpdates,
          );

          // Clear updates and reload traces to get fresh data
          set({ qualityUpdates: {} });
          await get().loadTraces(state.currentPage);
        } catch (error) {
          set({
            loading: false,
            error: error instanceof Error ? error.message : "Failed to save quality updates",
          });
        }
      },

      // Clear all data
      clear: () =>
        set({
          projectData: null,
          traces: [],
          totalTraces: 0,
          availableFeatures: [],
          qualityUpdates: {},
          error: null,
        }),

      // Reset persisted state
      reset: () =>
        set({
          dataFolder: "",
          fov: 0,
          selectedFeature: "",
          currentPage: 0,
          projectData: null,
          traces: [],
          totalTraces: 0,
          availableFeatures: [],
          qualityUpdates: {},
          error: null,
        }),
    }),
    {
      name: "pyama:visualization",
      partialize: (state) => ({
        dataFolder: state.dataFolder,
        fov: state.fov,
        selectedFeature: state.selectedFeature,
        currentPage: state.currentPage,
      }),
    }
  )
);
