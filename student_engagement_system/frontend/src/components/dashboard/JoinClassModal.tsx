import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Modal } from '@/components/ui/Modal'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { classesApi } from '@/services/api/endpoints'

export function JoinClassModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const joinMutation = useMutation({
    mutationFn: classesApi.join,

    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['classes'] })
      setCode('')
      setError(null)
      onClose()
      navigate(`/student/lobby/${result.class_id}`)
    },

    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Unable to join classroom')
    },
  })

  const handleClose = () => {
    setError(null)
    onClose()
  }

  return (
    <Modal open={open} onClose={handleClose} title="Join a class">
      <div className="space-y-5">
        <div>
          <Label>Class code</Label>
          <Input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="e.g. PLSJPR"
            autoFocus
          />
          {error && <p className="mt-2 text-sm text-critical-500">{error}</p>}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button
            onClick={() => joinMutation.mutate(code.trim())}
            loading={joinMutation.isPending}
            disabled={!code.trim()}
          >
            Join
          </Button>
        </div>
      </div>
    </Modal>
  )
}
