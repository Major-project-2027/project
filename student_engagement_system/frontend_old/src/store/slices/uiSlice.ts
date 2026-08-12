import { createSlice, type PayloadAction } from '@reduxjs/toolkit'

interface UiState {
  sidebarCollapsed: boolean
  notificationsPanelOpen: boolean
}

const initialState: UiState = {
  sidebarCollapsed: false,
  notificationsPanelOpen: false,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed
    },
    setNotificationsPanel: (state, action: PayloadAction<boolean>) => {
      state.notificationsPanelOpen = action.payload
    },
  },
})

export const { toggleSidebar, setNotificationsPanel } = uiSlice.actions
export default uiSlice.reducer
