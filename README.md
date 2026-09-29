# Social Lens — collecte TikTok publique

Ce programme récupère les métadonnées publiques de vidéos TikTok, sans télécharger les vidéos, et alimente les bases Notion existantes **Publications Social Lens** et **Historique Social Lens**. Il ne demande pas au client de connecter son compte TikTok. La disponibilité des données publiques dépend de TikTok et de `yt-dlp` : la collecte peut échouer ou ne renvoyer que certains compteurs.

## Mise en route

1. Créer un dépôt GitHub pour ces fichiers (`collect.py`, `requirements.txt`, `.github/workflows/collect.yml`). Un dépôt public utilise normalement les minutes standard GitHub Actions gratuitement ; vérifier les conditions du compte avant l'activation.
2. Dans Notion, donner accès aux deux bases **Publications Social Lens** et **Historique Social Lens** à l'intégration interne Social Lens. Le plugin ChatGPT connecté n'est pas le jeton API du programme.
3. Dans **GitHub → Settings → Secrets and variables → Actions → Secrets**, créer `NOTION_TOKEN` avec le secret de l'intégration interne Notion. Ne jamais placer ce jeton dans le dépôt ni dans une conversation.
4. Dans **Variables**, créer `TIKTOK_ACCOUNTS` avec `qoblex.algeria`. Créer `TIKTOK_BRANDS_JSON` avec `{"qoblex.algeria":"Qoblex Algeria"}`. Pour d'autres marques, séparer les comptes par une virgule et ajouter la correspondance au JSON.
5. Dans l'onglet **Actions**, lancer **Social Lens TikTok → Run workflow**. Vérifier les journaux et les lignes Notion. Le déclenchement automatique est prévu à 08:15 en Algérie chaque jour, après publication du workflow sur la branche par défaut.

## Données

- **Publications** : titre, lien, date si fournie, réseau, marque, vues, likes, commentaires, partages et somme des interactions connues. Clé unique = URL canonique TikTok.
- **Historique** : relevé quotidien des vues, likes, commentaires et interactions. Clé unique = `tiktok:compte:id:AAAA-MM-JJ` ; un second lancement le même jour met à jour ce relevé.
- Les mesures absentes restent vides : une mesure indisponible n'est pas un zéro. La somme des interactions ne couvre que les mesures disponibles. Les partages ne sont pas stockés dans Historique car cette base n'a pas ce champ.
- Le programme n'efface aucune ligne Notion. Il ne renseigne pas encore `Dernière collecte` dans **Chaînes**, dont le champ `ID YouTube` concerne l'automatisation YouTube actuelle.

## Limites

La collecte `yt-dlp` de profils publics TikTok n'est pas une API officielle stable ; elle peut être bloquée ou changer sans préavis. Tester d'abord sur le compte Qoblex. Si aucune vidéo exploitable n'est reçue, l'exécution échoue et aucune ligne du compte n'est modifiée. La collecte historique commence à la date de la première exécution ; les compteurs passés ne sont pas reconstituables.
