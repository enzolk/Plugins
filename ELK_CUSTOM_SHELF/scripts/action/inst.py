# ELK_META {"label": "Inst", "short_name": "", "tooltip": "searchReplaceNames \"$\" \"_Mast\" \"selected\";\ninstance; move -r 50 0 0;\nsearchReplaceNames \"_Mast1\" \"_Inst\" \"selected\";", "source": "mel"}
global proc createAndRenameInstance() {
    // tape 1 : Vrifier la slection
    string $selection[] = `ls -sl`;
    if (size($selection) == 0) {
        error "Veuillez slectionner un objet avant d'excuter ce script.";
        return;
    }

    // Obtenir le nom de l'objet d'origine
    string $originalName = $selection[0];
    string $suffix = "_Inst";

    // Vrifier si l'objet d'origine a dj le suffixe _Inst
    int $hasSuffix = `gmatch $originalName ("*" + $suffix)`;

    // tape 2 : Crer une instance de l'objet slectionn
    string $instance[] = `instance`;

    // Vrifier qu'une instance a bien t cre
    if (size($instance) == 0) {
        error "Impossible de crer une instance.";
        return;
    }

    // tape 3 : Retirer l'instance de tous les groupes/hirarchies
    string $instanceName = $instance[0];
    parent -w $instanceName; // Dplace l'instance  la racine de la scne

    // tape 4 : Renommer l'instance avec le suffixe _Inst uniquement si ncessaire
    string $newName;
    if ($hasSuffix) {
        $newName = $originalName; // Garder le nom tel quel
    } else {
        $newName = $originalName + $suffix; // Ajouter le suffixe _Inst
    }
    rename $instanceName $newName;

    // tape 5 : Dplacer l'instance
    move -r 5 0 0;

    print ("Instance cre, retire de tous les groupes, et renomme en : " + $newName + "\n");
}

// Excuter la procdure
createAndRenameInstance();
