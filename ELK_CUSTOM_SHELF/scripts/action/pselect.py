# ELK_META {"label": "PSelect", "short_name": "", "tooltip": "This MEL script selects parent groups associated with selected objects, or the objects themselves if no parent group is found.", "source": "mel"}
string $selectedObjs[] = `ls -sl`;
if (size($selectedObjs) == 0) {
    warning "Please select one or more objects.";
} else {
    string $parentGroups[]; // Array to store parent groups

    // Iterate through each selected object
    for ($obj in $selectedObjs) {
        string $parentGroup[] = `listRelatives -p -f $obj`;
        if (size($parentGroup) != 0) {
            // Add parent group to the array if found
            $parentGroups[size($parentGroups)] = $parentGroup[0];
        } else {
            // If no parent group found, select the object itself
            $parentGroups[size($parentGroups)] = $obj;
        }
    }

    // Check if any parent groups were found
    if (size($parentGroups) == 0) {
        warning ("Selected object(s) have no parent groups.");
    } else {
        // Select all parent groups or objects
        select -r $parentGroups;
    }
}
