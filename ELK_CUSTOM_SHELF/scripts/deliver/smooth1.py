# ELK_META {"label": "smooth1", "short_name": "", "tooltip": "{\n//Lists the transform nodes of all selected objects\nstring $no...", "source": "mel"}
{
//Lists the transform nodes of all selected objects
string $nodes[] = `ls -selection`;

for ($node in $nodes)
{
//Loop through each object and obtain its shape node
string $shapes[] = `listRelatives -shapes $node`;

//Set the visibility attribute of each shape node to 0
//The shape node is saved to the 1st (or 0th) element of the $shape array
setAttr ($shapes[0] + ".smoothLevel") (1);
}
}