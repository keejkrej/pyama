import { Sample } from "@/types/processing";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { X, Plus } from "lucide-react";

interface SampleManagerProps {
  samples: Sample[];
  addSample: () => void;
  removeSample: (id: string) => void;
  updateSample: (id: string, field: "name" | "fovs", value: string) => void;
  onLoadYaml: () => void;
  onSaveYaml: () => void;
}

export function SampleManager({
  samples,
  addSample,
  removeSample,
  updateSample,
  onLoadYaml,
  onSaveYaml,
}: SampleManagerProps) {
  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="text-sm font-semibold text-neutral-50">
              Assign FOVs
            </CardTitle>
            <p className="text-xs text-neutral-400">
              Map samples to FOV ranges
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={addSample}>
            <Plus className="mr-1 h-3 w-3" />
            Add Sample
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-neutral-800 overflow-hidden">
          <Table>
            <TableHeader className="bg-neutral-800">
              <TableRow className="border-neutral-800 hover:bg-neutral-800">
                <TableHead className="text-neutral-300 h-9">Sample Name</TableHead>
                <TableHead className="text-neutral-300 h-9">FOVs</TableHead>
                <TableHead className="w-[50px] h-9"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="bg-neutral-900">
              {samples.map((sample) => (
                <TableRow
                  key={sample.id}
                  className="hover:bg-neutral-800/50 border-neutral-800"
                >
                  <TableCell className="py-2">
                    <Input
                      value={sample.name}
                      onChange={(e) =>
                        updateSample(sample.id, "name", e.target.value)
                      }
                      placeholder="Sample name"
                      className="h-7 bg-transparent border-transparent hover:border-neutral-700 focus:border-neutral-500 px-1"
                    />
                  </TableCell>
                  <TableCell className="py-2">
                    <Input
                      value={sample.fovs}
                      onChange={(e) =>
                        updateSample(sample.id, "fovs", e.target.value)
                      }
                      placeholder="e.g. 0-5, 7, 9-11"
                      className="h-7 bg-transparent border-transparent hover:border-neutral-700 focus:border-neutral-500 px-1"
                    />
                  </TableCell>
                  <TableCell className="py-2 text-right">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6 hover:text-red-400"
                      onClick={() => removeSample(sample.id)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {samples.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="h-24 text-center text-neutral-500 text-xs"
                  >
                    No samples defined. Click "Add Sample" to create one.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={onLoadYaml}>
            Load from YAML
          </Button>
          <Button size="sm" variant="outline" onClick={onSaveYaml}>
            Save to YAML
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
