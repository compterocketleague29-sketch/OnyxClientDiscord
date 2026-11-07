import type { Metadata } from 'next'
import { LegalPage, type LegalSection } from '@/components/legal-page'

export const metadata: Metadata = {
  title: "Conditions Générales d'Utilisation — Onyx Client",
  description: "Conditions Générales d'Utilisation du site et du logiciel Onyx Client.",
}

const sections: LegalSection[] = [
  {
    title: 'Objet',
    paragraphs: [
      "Les présentes Conditions Générales d'Utilisation (CGU) définissent les règles d'accès et d'utilisation du site Onyx Client (« le Site ») et du logiciel Onyx Client (« le Logiciel »).",
      "En créant un compte ou en utilisant le Logiciel, l'utilisateur accepte sans réserve les présentes CGU.",
    ],
  },
  {
    title: 'Accès au Site',
    paragraphs: [
      "Le Site est accessible gratuitement. La création d'un compte est nécessaire pour acheter une licence et consulter ses clés.",
      "Le Vendeur peut suspendre l'accès au Site pour maintenance ou mise à jour, sans que cela ouvre droit à indemnisation.",
    ],
  },
  {
    title: 'Compte utilisateur',
    paragraphs: [
      "L'utilisateur s'engage à fournir une adresse e-mail valide et à garder son mot de passe confidentiel. Il est responsable de toute activité réalisée depuis son compte.",
      "En cas d'utilisation frauduleuse de son compte, l'utilisateur doit prévenir le Vendeur sans délai.",
    ],
  },
  {
    title: 'Licence d’utilisation',
    paragraphs: [
      "L'achat d'une clé confère à l'utilisateur un droit d'utilisation personnel, non exclusif et non transférable du Logiciel, pour la durée de la licence achetée.",
      "Une clé est associée au premier ordinateur sur lequel elle est activée. Un changement de machine peut être demandé au support.",
    ],
  },
  {
    title: 'Interdictions',
    paragraphs: [
      "Il est strictement interdit de : partager, revendre ou céder une clé ; décompiler, désassembler, modifier ou tenter de contourner le système de licence du Logiciel ; redistribuer le fichier .exe ; utiliser le Site ou le Logiciel à des fins illégales.",
      "Tout manquement entraîne la révocation immédiate de la clé concernée, sans remboursement, et peut entraîner la suppression du compte.",
    ],
  },
  {
    title: 'Utilisation en jeu',
    paragraphs: [
      "Onyx Client n'est ni affilié, ni approuvé par Psyonix ou Epic Games. Rocket League est une marque déposée de Psyonix LLC.",
      "L'utilisation de macros peut être contraire aux règles du jeu et des compétitions en ligne. L'utilisateur reconnaît en connaître les risques (y compris le bannissement de son compte) et utilise le Logiciel sous sa seule responsabilité.",
    ],
  },
  {
    title: 'Propriété intellectuelle',
    paragraphs: [
      "Le Logiciel, le Site, le logo Onyx Client et l'ensemble de leurs contenus sont la propriété exclusive du Vendeur. Toute reproduction ou exploitation non autorisée est interdite.",
    ],
  },
  {
    title: 'Responsabilité',
    paragraphs: [
      "Le Logiciel est fourni « en l'état ». Le Vendeur s'efforce d'en assurer le bon fonctionnement mais ne garantit pas sa compatibilité permanente avec les mises à jour du jeu ou du système d'exploitation.",
      "Le Vendeur ne pourra être tenu responsable des dommages indirects liés à l'utilisation du Logiciel, notamment la perte de progression ou la sanction d'un compte de jeu.",
    ],
  },
  {
    title: 'Données personnelles',
    paragraphs: [
      "Les données traitées et les droits de l'utilisateur sont décrits dans les Conditions Générales de Vente (article « Données personnelles »). Le Site utilise uniquement des cookies nécessaires à la connexion et au panier.",
    ],
  },
  {
    title: 'Modification des CGU',
    paragraphs: [
      "Le Vendeur peut modifier les présentes CGU à tout moment. La version applicable est celle en ligne au moment de l'utilisation du Site ou du Logiciel.",
    ],
  },
  {
    title: 'Droit applicable',
    paragraphs: [
      "Les présentes CGU sont soumises au droit français. Tout litige relève des juridictions françaises compétentes, après tentative de résolution amiable.",
    ],
  },
]

export default function CguPage() {
  return (
    <LegalPage
      eyebrow="Légal"
      title="Conditions Générales d'Utilisation"
      updatedAt="11 avril 2026"
      intro="Ces conditions encadrent l'utilisation du site et du logiciel Onyx Client."
      sections={sections}
      otherDoc={{ href: '/cgv', label: 'Conditions Générales de Vente' }}
    />
  )
}
