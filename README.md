# Odin

Loop

1. Open one debugger connection
2. Set breakpoint at Game.onUpdate
3. Northgard reaches it and stops
4. Save the current Game.onUpdate frame
5. Remove the breakpoint
6. Observe and act using that saved frame
7. Continue Northgard
8. Let it run for 0.5 seconds
9. Set the Game.onUpdate breakpoint again
10. Northgard stops and provides a new frame
11. Repeat from step 4


Python action or observation
        ↓
Our JavaScript native-call fix
        ↓
Existing HashLink adapter machinery
        ↓
Northgard debug connection
        ↓
Native function executes inside Northgard